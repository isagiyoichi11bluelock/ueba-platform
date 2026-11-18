"""Tests for rule-based indicators."""
from __future__ import annotations
import pytest
import sqlite3
from datetime import date
from src.ueba.db import initialize_db
from src.ueba.indicators import (
    check_unusual_hour, check_new_country, check_failed_login_burst_then_success,
    check_download_volume_spike, check_impossible_travel, check_new_device,
    compute_indicators,
)
from src.ueba.config import load_scoring_weights


@pytest.fixture
def test_db():
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


def test_unusual_hour_fires_at_night(test_db):
    """UNUSUAL_HOUR fires when user logs in at 03:00 and baseline shows 09:00-17:00."""
    baseline = {"typical_start_hour": 9, "typical_end_hour": 17, "confidence": 1.0}
    target_date = date(2024, 2, 1)
    test_db.execute(
        """INSERT INTO login_events VALUES ('L-001', '2024-02-01T03:00:00', 'E0001', 
           'U-TEST01', '10.0.0.1', '10.0.0.0/24', 'US', 'New York', 'DEV-E0001-1',
           'success', 'password', 'sess-001', 0)"""
    )
    test_db.commit()
    weights = load_scoring_weights()
    indicators = check_unusual_hour(test_db, "E0001", target_date, baseline, {}, weights)
    assert any(i["name"] == "UNUSUAL_HOUR" for i in indicators)


def test_unusual_hour_does_not_fire_in_hours(test_db):
    """UNUSUAL_HOUR does not fire when user logs in during normal hours."""
    baseline = {"typical_start_hour": 9, "typical_end_hour": 17, "confidence": 1.0}
    target_date = date(2024, 2, 1)
    test_db.execute(
        """INSERT INTO login_events VALUES ('L-002', '2024-02-01T10:00:00', 'E0001',
           'U-TEST01', '10.0.0.1', '10.0.0.0/24', 'US', 'New York', 'DEV-E0001-1',
           'success', 'password', 'sess-002', 0)"""
    )
    test_db.commit()
    weights = load_scoring_weights()
    indicators = check_unusual_hour(test_db, "E0001", target_date, baseline, {}, weights)
    assert not any(i["name"] == "UNUSUAL_HOUR" for i in indicators)


def test_new_country_fires(test_db):
    baseline = {"known_countries": ["US"], "known_cities": ["New York"], "confidence": 1.0}
    target_date = date(2024, 2, 1)
    test_db.execute(
        """INSERT INTO login_events VALUES ('L-003', '2024-02-01T10:00:00', 'E0001',
           'U-TEST01', '10.0.0.1', '10.0.0.0/24', 'DE', 'Berlin', 'DEV-E0001-1',
           'success', 'password', 'sess-003', 0)"""
    )
    test_db.commit()
    weights = load_scoring_weights()
    indicators = check_new_country(test_db, "E0001", target_date, baseline, {}, weights)
    assert any(i["name"] == "NEW_COUNTRY" for i in indicators)


def test_failed_login_burst_fires(test_db):
    target_date = date(2024, 2, 1)
    baseline = {"failed_login_rate": 0.05, "confidence": 1.0}
    for i in range(6):
        ts = f"2024-02-01T10:0{i}:00"
        test_db.execute(
            f"""INSERT INTO login_events VALUES ('L-F{i:02d}', '{ts}', 'E0001',
               'U-TEST01', '10.0.0.1', '10.0.0.0/24', 'US', 'New York', 'DEV-E0001-1',
               'failure', 'password', 'sess-fail', 0)"""
        )
    # Then success
    test_db.execute(
        """INSERT INTO login_events VALUES ('L-S00', '2024-02-01T10:07:00', 'E0001',
           'U-TEST01', '10.0.0.1', '10.0.0.0/24', 'US', 'New York', 'DEV-E0001-1',
           'success', 'password', 'sess-suc', 0)"""
    )
    test_db.commit()
    weights = load_scoring_weights()
    indicators = check_failed_login_burst_then_success(test_db, "E0001", target_date, baseline, {}, weights)
    assert any(i["name"] == "FAILED_LOGIN_BURST_THEN_SUCCESS" for i in indicators)


def test_download_spike_fires(test_db):
    baseline = {
        "download_median_bytes": 1_000_000,
        "download_mad_bytes": 200_000,
        "confidence": 1.0,
    }
    target_date = date(2024, 2, 1)
    test_db.execute("INSERT OR IGNORE INTO resources VALUES ('RES-0001', 'code_repo', 'Internal', 'Developer', 'Test Repo')")
    test_db.execute(
        """INSERT INTO download_events VALUES ('D-001', '2024-02-01T10:00:00', 'E0001',
           'U-TEST01', 'sess-dl', 'RES-0001', 2000000000, 100, 'managed_laptop', 0)"""
    )
    test_db.commit()
    weights = load_scoring_weights()
    indicators = check_download_volume_spike(test_db, "E0001", target_date, baseline, {}, weights)
    assert any(i["name"] == "DOWNLOAD_VOLUME_SPIKE" for i in indicators)


def test_new_device_fires(test_db):
    baseline = {"known_devices": ["DEV-E0001-1"], "confidence": 1.0}
    target_date = date(2024, 2, 1)
    test_db.execute(
        """INSERT INTO login_events VALUES ('L-004', '2024-02-01T10:00:00', 'E0001',
           'U-TEST01', '10.0.0.1', '10.0.0.0/24', 'US', 'New York', 'NEW-DEV-999',
           'success', 'password', 'sess-004', 0)"""
    )
    test_db.commit()
    weights = load_scoring_weights()
    indicators = check_new_device(test_db, "E0001", target_date, baseline, {}, weights)
    assert any(i["name"] == "NEW_DEVICE" for i in indicators)
