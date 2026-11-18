"""Tests for baseline computation."""
from __future__ import annotations
import pytest
import sqlite3
from datetime import date, timedelta
from src.ueba.db import initialize_db
from src.ueba.baseline import compute_user_baseline, blend_baselines


@pytest.fixture
def temp_db():
    """Create a fresh in-memory DB for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_db(conn)
    # Insert a test user
    conn.execute(
        """INSERT INTO users (user_id, pseudonym, role, department, home_country, home_city,
           hire_date, work_start_hour, work_end_hour, timezone, working_days,
           is_manager, is_contractor, is_night_shift, is_part_time)
           VALUES ('E0001', 'U-TEST01', 'Developer', 'Engineering', 'US', 'New York',
           '2023-01-01', 9, 17, 'UTC', '[0,1,2,3,4]', 0, 0, 0, 0)"""
    )
    # Insert some login events in baseline period
    base_date = date(2024, 1, 15)
    for i in range(30):
        d = base_date - timedelta(days=i+1)
        conn.execute(
            """INSERT INTO login_events (event_id, timestamp, user_id, pseudonym_id, source_ip, 
               source_ip_truncated, country, city, device_id, auth_result, auth_method, session_id)
               VALUES (?, ?, 'E0001', 'U-TEST01', '10.0.0.1', '10.0.0.0/24', 'US', 'New York',
               'DEV-E0001-1', 'success', 'password', 'sess-' || ?)""",
            (f"L-{i:04d}", f"{d.isoformat()}T10:00:00", f"sess-{i}")
        )
    conn.commit()
    return conn


def test_baseline_computes(temp_db):
    bl = compute_user_baseline(temp_db, "E0001", date(2024, 1, 15))
    assert "confidence" in bl
    assert "hour_histogram" in bl
    assert bl["confidence"] > 0


def test_no_data_leakage(temp_db):
    """Baseline on day X must not use events from day X onwards."""
    temp_db.execute(
        """INSERT INTO login_events (event_id, timestamp, user_id, pseudonym_id, source_ip,
           source_ip_truncated, country, city, device_id, auth_result, auth_method, session_id)
           VALUES ('FUTURE', '2024-01-16T03:00:00', 'E0001', 'U-TEST01', '192.168.1.1',
           '192.168.1.0/24', 'DE', 'Berlin', 'NEW-DEVICE', 'success', 'password', 'sess-future')"""
    )
    temp_db.commit()
    bl = compute_user_baseline(temp_db, "E0001", date(2024, 1, 16))
    assert "DE" not in bl.get("known_countries", [])


def test_blend_baselines_full_confidence():
    user_bl = {"download_median_bytes": 100.0, "confidence": 1.0}
    role_bl = {"download_median_bytes": 500.0}
    blended = blend_baselines(user_bl, role_bl, confidence=1.0)
    assert blended["download_median_bytes"] == pytest.approx(100.0)


def test_blend_baselines_zero_confidence():
    user_bl = {"download_median_bytes": 100.0, "confidence": 0.0}
    role_bl = {"download_median_bytes": 500.0}
    blended = blend_baselines(user_bl, role_bl, confidence=0.0)
    assert blended["download_median_bytes"] == pytest.approx(500.0)


def test_blend_baselines_partial_confidence():
    user_bl = {"download_median_bytes": 100.0}
    role_bl = {"download_median_bytes": 500.0}
    blended = blend_baselines(user_bl, role_bl, confidence=0.5)
    assert blended["download_median_bytes"] == pytest.approx(300.0)
