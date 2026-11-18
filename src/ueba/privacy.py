"""Privacy utilities: pseudonymization, minimization, retention."""
from __future__ import annotations
import hashlib
import hmac
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional
from .config import get_config, get_pseudonym_salt


def pseudonymize_user_id(user_id: str, salt: str | None = None) -> str:
    """Generate a stable pseudonym for a user ID using HMAC-SHA256."""
    if salt is None:
        salt = get_pseudonym_salt()
    h = hmac.new(salt.encode(), user_id.encode(), hashlib.sha256).hexdigest()
    cfg = get_config()
    return f"{cfg.privacy.pseudonym_prefix}{h[:6].upper()}"


def truncate_ip(ip: str) -> str:
    """Truncate IPv4 to /24 (drop last octet) for privacy."""
    cfg = get_config()
    if not cfg.privacy.ip_truncation:
        return ip
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return ip  # IPv6 or malformed — return as-is


def sanitize_comment(text: str, max_chars: int | None = None) -> str:
    """Sanitize analyst comment: strip dangerous chars, truncate."""
    cfg = get_config()
    if max_chars is None:
        max_chars = cfg.feedback.max_comment_chars
    # Remove any HTML/script tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove null bytes
    text = text.replace('\x00', '')
    # Truncate
    return text[:max_chars]


def store_pseudonym_mapping(conn: sqlite3.Connection, user_id: str, pseudonym: str) -> None:
    """Store user_id -> pseudonym mapping in the separate pseudonym_map table."""
    conn.execute(
        "INSERT OR IGNORE INTO pseudonym_map (user_id, pseudonym, created_at) VALUES (?, ?, ?)",
        (user_id, pseudonym, datetime.utcnow().isoformat())
    )


def get_pseudonym(conn: sqlite3.Connection, user_id: str) -> str:
    """Get or create pseudonym for user_id."""
    row = conn.execute("SELECT pseudonym FROM pseudonym_map WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return row[0]
    pseudonym = pseudonymize_user_id(user_id)
    store_pseudonym_mapping(conn, user_id, pseudonym)
    conn.commit()
    return pseudonym


def request_reidentification(
    conn: sqlite3.Connection,
    pseudonym: str,
    requester: str,
    requester_role: str,
    justification: str,
    audit_fn: callable,
) -> dict:
    """
    Gated re-identification: only senior_analyst role, requires justification >= 20 chars.
    Returns internal user_id only (no extra personal attributes).
    """
    cfg = get_config()
    if requester_role != cfg.privacy.identity_map_access_role:
        raise PermissionError(
            f"Re-identification requires role '{cfg.privacy.identity_map_access_role}'"
        )
    if len(justification) < cfg.privacy.min_justification_chars:
        raise ValueError(
            f"Justification must be at least {cfg.privacy.min_justification_chars} characters"
        )

    row = conn.execute(
        "SELECT user_id FROM pseudonym_map WHERE pseudonym = ?", (pseudonym,)
    ).fetchone()
    if not row:
        raise KeyError(f"No identity found for pseudonym {pseudonym}")

    # Audit this access
    audit_entry_id = audit_fn(
        conn=conn,
        actor=requester,
        action="REIDENTIFICATION_REQUEST",
        details={
            "pseudonym": pseudonym,
            "justification": justification,
            "requester_role": requester_role,
        },
    )

    # Log to identity_map_access_log
    conn.execute(
        """INSERT INTO identity_map_access_log
           (access_id, pseudonym, accessed_by, justification, timestamp, audit_entry_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            pseudonym,
            requester,
            justification,
            datetime.utcnow().isoformat(),
            audit_entry_id,
        ),
    )
    conn.commit()

    return {"user_id": row[0], "note": "Internal ID only. No further personal data returned."}


def purge_expired_events(conn: sqlite3.Connection, dry_run: bool = False) -> dict[str, int]:
    """Purge events older than retention period."""
    cfg = get_config()
    cutoffs = {
        "login_events":       datetime.utcnow() - timedelta(days=cfg.retention.events_days),
        "file_access_events": datetime.utcnow() - timedelta(days=cfg.retention.events_days),
        "download_events":    datetime.utcnow() - timedelta(days=cfg.retention.events_days),
        "privilege_events":   datetime.utcnow() - timedelta(days=cfg.retention.events_days),
        "alerts":             datetime.utcnow() - timedelta(days=cfg.retention.alerts_days),
        "audit_log":          datetime.utcnow() - timedelta(days=cfg.retention.audit_days),
    }
    ts_cols = {
        "login_events":       "timestamp",
        "file_access_events": "timestamp",
        "download_events":    "timestamp",
        "privilege_events":   "timestamp",
        "alerts":             "alert_date",
        "audit_log":          "timestamp",
    }
    counts: dict[str, int] = {}
    for table, cutoff in cutoffs.items():
        ts_col = ts_cols[table]
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {ts_col} < ?",
            (cutoff.isoformat(),),
        ).fetchone()
        counts[table] = row[0]
        if not dry_run and row[0] > 0:
            conn.execute(
                f"DELETE FROM {table} WHERE {ts_col} < ?",
                (cutoff.isoformat(),),
            )
    if not dry_run:
        conn.commit()
    return counts
