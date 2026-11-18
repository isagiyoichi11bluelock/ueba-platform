"""Tests for analyst feedback loop."""
from __future__ import annotations
import pytest
import sqlite3
from src.ueba.db import initialize_db
from src.ueba.feedback import submit_feedback, get_adjustment_factor, expire_old_rules, get_feedback_stats


@pytest.fixture
def feedback_db():
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
    conn.execute(
        """INSERT INTO alerts (alert_id, user_id, pseudonym_id, alert_date, risk_score,
           severity_band, indicators_json, context_applied_json, summary, baseline_confidence, status)
           VALUES ('ALT-001', 'E0001', 'U-TEST01', '2024-02-01', 75.0, 'high', '[]', '[]',
           'Test alert', 0.8, 'open')"""
    )
    conn.commit()
    return conn


def test_submit_feedback_valid_verdict(feedback_db):
    fid = submit_feedback(feedback_db, "ALT-001", "analyst1", "benign_expected", "It was planned work")
    assert fid is not None


def test_submit_feedback_invalid_verdict(feedback_db):
    with pytest.raises(ValueError):
        submit_feedback(feedback_db, "ALT-001", "analyst1", "invalid_verdict", "")


def test_feedback_updates_alert_status(feedback_db):
    submit_feedback(feedback_db, "ALT-001", "analyst1", "confirmed_suspicious", "Confirmed threat")
    row = feedback_db.execute("SELECT status FROM alerts WHERE alert_id = 'ALT-001'").fetchone()
    assert row[0] == "confirmed_suspicious"


def test_adjustment_factor_default_is_1(feedback_db):
    factor = get_adjustment_factor(feedback_db, "E0001", "UNUSUAL_HOUR")
    assert factor == 1.0


def test_feedback_stats(feedback_db):
    submit_feedback(feedback_db, "ALT-001", "analyst1", "benign_expected", "Planned")
    stats = get_feedback_stats(feedback_db)
    assert stats["total_reviewed"] == 1
    assert "benign_expected" in stats["by_verdict"]
