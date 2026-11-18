"""Tamper-evident append-only audit log with SHA-256 hash chain."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any


def _canonical_json(obj: dict) -> str:
    """Produce canonical JSON for hashing (sorted keys)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True)


def _compute_hash(prev_hash: str, entry_data: dict) -> str:
    """Compute SHA-256 hash of prev_hash + canonical entry data."""
    payload = prev_hash + _canonical_json(entry_data)
    return hashlib.sha256(payload.encode()).hexdigest()


def log_audit_event(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    details: dict[str, Any],
) -> str:
    """
    Append a tamper-evident entry to the audit log.
    Returns the new entry_id.
    """
    entry_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    # Get previous hash (most recent by timestamp)
    row = conn.execute(
        "SELECT entry_hash FROM audit_log ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    prev_hash = row[0] if row else "0" * 64

    entry_data = {
        "entry_id": entry_id,
        "timestamp": timestamp,
        "actor": actor,
        "action": action,
        "details": details,
    }
    entry_hash = _compute_hash(prev_hash, entry_data)

    conn.execute(
        """INSERT INTO audit_log (entry_id, timestamp, actor, action, details_json, prev_hash, entry_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            entry_id,
            timestamp,
            actor,
            action,
            _canonical_json(details),
            prev_hash,
            entry_hash,
        ),
    )
    conn.commit()
    return entry_id


def verify_audit_chain(conn: sqlite3.Connection) -> dict:
    """
    Verify the integrity of the audit log hash chain.
    Returns {'valid': bool, 'entries_checked': int, 'first_broken_entry': str | None}
    """
    rows = conn.execute(
        """SELECT entry_id, timestamp, actor, action, details_json, prev_hash, entry_hash
           FROM audit_log ORDER BY timestamp ASC"""
    ).fetchall()

    if not rows:
        return {"valid": True, "entries_checked": 0, "first_broken_entry": None}

    expected_prev = "0" * 64
    for idx, row in enumerate(rows):
        entry_data = {
            "entry_id": row[0],
            "timestamp": row[1],
            "actor": row[2],
            "action": row[3],
            "details": json.loads(row[4]),
        }
        if row[5] != expected_prev:
            return {
                "valid": False,
                "entries_checked": idx,
                "first_broken_entry": row[0],
            }

        expected_hash = _compute_hash(row[5], entry_data)
        if row[6] != expected_hash:
            return {
                "valid": False,
                "entries_checked": idx,
                "first_broken_entry": row[0],
            }

        expected_prev = row[6]

    return {"valid": True, "entries_checked": len(rows), "first_broken_entry": None}


def tamper_audit_entry(conn: sqlite3.Connection, entry_id: str, new_details: dict) -> None:
    """FOR TESTING ONLY: Tamper with an audit entry without updating the hash."""
    conn.execute(
        "UPDATE audit_log SET details_json = ? WHERE entry_id = ?",
        (_canonical_json(new_details), entry_id),
    )
    conn.commit()
