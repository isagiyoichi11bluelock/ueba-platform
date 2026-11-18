"""Tests for risk scoring."""
from __future__ import annotations
import pytest
import sqlite3
from datetime import date
from src.ueba.db import initialize_db
from src.ueba.scoring import _diminishing_returns_score, _get_severity_band, compute_risk_score


def test_diminishing_returns_empty():
    assert _diminishing_returns_score([]) == 0.0


def test_diminishing_returns_single():
    score = _diminishing_returns_score([50.0])
    assert pytest.approx(score, abs=1) == 50.0


def test_diminishing_returns_does_not_saturate_quickly():
    score = _diminishing_returns_score([10.0] * 20)
    assert score < 95.0


def test_diminishing_returns_capped_at_100():
    score = _diminishing_returns_score([100.0, 100.0, 100.0])
    assert score <= 100.0


def test_severity_band_low():
    assert _get_severity_band(20.0) == "low"


def test_severity_band_medium():
    assert _get_severity_band(45.0) == "medium"


def test_severity_band_high():
    assert _get_severity_band(70.0) == "high"


def test_severity_band_critical():
    assert _get_severity_band(85.0) == "critical"


@pytest.fixture
def alert_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_db(conn)
    conn.execute(
        """INSERT INTO users (user_id, pseudonym, role, department, home_country, home_city,
           hire_date, work_start_hour, work_end_hour, timezone, working_days,
           is_manager, is_contractor, is_night_shift, is_part_time)
           VALUES ('E0001', 'U-TEST01', 'Developer', 'Engineering', 'US', 'New York',
           '2023-01-01', 9, 17, 'UTC', '[0,1,2,3,4]', 0, 0, 0, 0)"""
    )
    conn.commit()
    return conn


def test_compute_risk_score_saves_alert(alert_db):
    indicators = [{
        "indicator_id": "test-1",
        "name": "UNUSUAL_HOUR",
        "severity_points": 20.0,
        "confidence": 0.9,
        "description": "Test indicator",
        "evidence_event_ids": ["L-001"],
        "observed_value": 3,
        "baseline_value": 10,
        "why_it_matters": "Test",
    }]
    result = compute_risk_score(
        user_id="E0001",
        pseudonym_id="U-TEST01",
        alert_date=date(2024, 2, 1),
        indicators=indicators,
        context_applied=[],
        baseline_confidence=0.8,
        conn=alert_db,
    )
    assert result["risk_score"] > 0
    assert result["alert_id"] is not None
    row = alert_db.execute("SELECT * FROM alerts WHERE alert_id = ?", (result["alert_id"],)).fetchone()
    assert row is not None
