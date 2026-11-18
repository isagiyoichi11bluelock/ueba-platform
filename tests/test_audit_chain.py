"""Tests for tamper-evident audit log."""
from __future__ import annotations
import pytest
import sqlite3
from src.ueba.db import initialize_db
from src.ueba.audit import log_audit_event, verify_audit_chain, tamper_audit_entry


@pytest.fixture
def audit_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_db(conn)
    return conn


def test_audit_chain_valid_on_empty(audit_db):
    result = verify_audit_chain(audit_db)
    assert result["valid"] is True
    assert result["entries_checked"] == 0


def test_audit_chain_valid_after_entries(audit_db):
    log_audit_event(audit_db, "analyst1", "LOGIN", {"ip": "10.0.0.1"})
    log_audit_event(audit_db, "analyst1", "VIEW_ALERT", {"alert_id": "abc"})
    log_audit_event(audit_db, "analyst2", "SUBMIT_VERDICT", {"verdict": "benign"})
    result = verify_audit_chain(audit_db)
    assert result["valid"] is True
    assert result["entries_checked"] == 3


def test_audit_chain_detects_tampering(audit_db):
    """Verify that tampering with an entry breaks the chain."""
    entry_id = log_audit_event(audit_db, "analyst1", "LOGIN", {"ip": "10.0.0.1"})
    log_audit_event(audit_db, "analyst1", "VIEW_ALERT", {"alert_id": "abc"})

    # Tamper with the first entry
    tamper_audit_entry(audit_db, entry_id, {"ip": "TAMPERED"})

    result = verify_audit_chain(audit_db)
    assert result["valid"] is False
    assert result["first_broken_entry"] is not None


def test_audit_entry_has_all_fields(audit_db):
    entry_id = log_audit_event(audit_db, "system", "PIPELINE_RUN", {"count": 42})
    row = audit_db.execute("SELECT * FROM audit_log WHERE entry_id = ?", (entry_id,)).fetchone()
    assert row is not None
    assert row["actor"] == "system"
    assert row["action"] == "PIPELINE_RUN"
    assert row["prev_hash"] is not None
    assert row["entry_hash"] is not None
    assert len(row["entry_hash"]) == 64


def test_audit_chain_multiple_entries_valid(audit_db):
    for i in range(10):
        log_audit_event(audit_db, f"user{i}", "ACTION", {"i": i})
    result = verify_audit_chain(audit_db)
    assert result["valid"] is True
    assert result["entries_checked"] == 10
