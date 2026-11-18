"""End-to-end scenario assertions against ground truth."""
from __future__ import annotations
import pytest
import sqlite3
from pathlib import Path
from src.ueba.db import get_connection, get_db_path
from src.ueba.evaluate import evaluate_against_ground_truth

DB_PATH = get_db_path()


@pytest.fixture(scope="module")
def prod_db():
    """Connect to the pre-generated DB (requires build_dataset + pipeline to have run)."""
    if not DB_PATH.exists():
        pytest.skip("Database not found - run build_dataset and pipeline first")
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM ground_truth").fetchone()[0]
    if count == 0:
        pytest.skip("No ground truth data - run build_dataset first")
    yield conn
    conn.close()


def _get_scenario_score(conn, scenario_id: str) -> float:
    """Get the highest risk score for a scenario in its injection window."""
    gt = conn.execute(
        "SELECT user_id, start_time, end_time FROM ground_truth WHERE scenario_id = ?",
        (scenario_id,)
    ).fetchone()
    if not gt:
        return 0.0

    row = conn.execute(
        """SELECT MAX(risk_score) FROM alerts
           WHERE user_id = ? AND alert_date >= ? AND alert_date <= ?""",
        (gt[0], gt[1][:10], gt[2][:10])
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def test_s1_compromised_credentials_high_score(prod_db):
    """S1: Compromised credentials must score >= 80 (Critical)."""
    score = _get_scenario_score(prod_db, "S1")
    assert score >= 80, f"S1 expected >= 80, got {score}"


def test_s2_data_hoarding_high_score(prod_db):
    """S2: Departing employee data hoarding must score >= 65."""
    score = _get_scenario_score(prod_db, "S2")
    assert score >= 65, f"S2 expected >= 65, got {score}"


def test_s3_contractor_scope_creep_medium_score(prod_db):
    """S3: Contractor scope creep must score >= 55."""
    score = _get_scenario_score(prod_db, "S3")
    assert score >= 55, f"S3 expected >= 55, got {score}"


def test_s4_benign_travel_low_score(prod_db):
    """S4: Approved business travel must score <= 35 after context dampening."""
    score = _get_scenario_score(prod_db, "S4")
    assert score <= 35, f"S4 expected <= 35 (benign after dampening), got {score}"


def test_s5_month_end_low_score(prod_db):
    """S5: Month-end close must score <= 35."""
    score = _get_scenario_score(prod_db, "S5")
    assert score <= 35, f"S5 expected <= 35 (benign month-end), got {score}"


def test_s6_new_joiner_medium_score(prod_db):
    """S6: New joiner cold start must score <= 45."""
    score = _get_scenario_score(prod_db, "S6")
    assert score <= 45, f"S6 expected <= 45 (new joiner low confidence), got {score}"


def test_s7_oncall_low_score(prod_db):
    """S7: On-call IT admin must score <= 35."""
    score = _get_scenario_score(prod_db, "S7")
    assert score <= 35, f"S7 expected <= 35 (on-call benign), got {score}"


def test_s8_no_context_high_score(prod_db):
    """S8: Same as S4 but no context - must score >= 60."""
    score = _get_scenario_score(prod_db, "S8")
    assert score >= 60, f"S8 expected >= 60 (no context), got {score}"


def test_s4_vs_s8_contrast(prod_db):
    """S4 (with context) must score substantially lower than S8 (no context)."""
    s4_score = _get_scenario_score(prod_db, "S4")
    s8_score = _get_scenario_score(prod_db, "S8")
    assert s8_score - s4_score >= 25, f"S4={s4_score}, S8={s8_score}: S8 must be >= 25 pts higher"


def test_evaluation_recall_malicious(prod_db):
    """Recall on malicious scenarios must be >= 0.85."""
    results = evaluate_against_ground_truth(prod_db)
    assert results["recall"] >= 0.85, f"Recall {results['recall']} < 0.85"


def test_benign_scenarios_not_critical(prod_db):
    """Benign scenarios (S4, S5, S6, S7) must not appear in High/Critical bands."""
    for s_id in ["S4", "S5", "S7"]:
        score = _get_scenario_score(prod_db, s_id)
        assert score <= 59, f"{s_id} should not be High/Critical, got {score}"


def test_all_malicious_scenarios_above_medium(prod_db):
    """All malicious scenarios must be above Low band."""
    for s_id in ["S1", "S2", "S3"]:
        score = _get_scenario_score(prod_db, s_id)
        assert score >= 35, f"{s_id} should be at least Medium, got {score}"
