"""Analyst feedback loop and adjustment rules."""
from __future__ import annotations
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional
from .config import get_config
from .privacy import sanitize_comment
from .audit import log_audit_event

VALID_VERDICTS = {"confirmed_suspicious", "benign_expected", "needs_more_info", "false_positive"}


def submit_feedback(
    conn: sqlite3.Connection,
    alert_id: str,
    analyst: str,
    verdict: str,
    comment: str = "",
    create_adjustment: bool = False,
    indicator_id: str | None = None,
) -> str:
    """Submit analyst verdict on an alert. Returns feedback_id."""
    cfg = get_config()
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"Invalid verdict. Must be one of: {VALID_VERDICTS}")

    comment = sanitize_comment(comment, cfg.feedback.max_comment_chars)
    feedback_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    conn.execute(
        """INSERT INTO analyst_feedback (feedback_id, alert_id, analyst, verdict, comment, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (feedback_id, alert_id, analyst, verdict, comment, now),
    )

    # Update alert status
    conn.execute(
        "UPDATE alerts SET status = ? WHERE alert_id = ?",
        (verdict, alert_id),
    )

    # Create adjustment rule if requested for benign_expected verdict
    rule_id = None
    if verdict == "benign_expected" and create_adjustment and indicator_id:
        rule_id = _create_adjustment_rule(conn, alert_id, analyst, indicator_id, comment)

    conn.commit()

    # Audit
    log_audit_event(
        conn,
        actor=analyst,
        action="ANALYST_FEEDBACK",
        details={
            "feedback_id": feedback_id,
            "alert_id": alert_id,
            "verdict": verdict,
            "adjustment_rule_id": rule_id,
        },
    )

    return feedback_id


def _create_adjustment_rule(
    conn: sqlite3.Connection,
    alert_id: str,
    analyst: str,
    indicator_id: str,
    reason: str,
) -> str:
    """Create a per-user, per-indicator adjustment rule."""
    cfg = get_config()

    # Get user_id from alert
    row = conn.execute("SELECT user_id FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
    if not row:
        raise KeyError(f"Alert {alert_id} not found")
    user_id = row[0]

    # Abuse prevention: max 10 active rules per user
    active_count = conn.execute(
        "SELECT COUNT(*) FROM adjustment_rules WHERE user_id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()[0]
    if active_count >= 10:
        raise ValueError("Maximum adjustment rules per user (10) reached")

    rule_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(days=cfg.feedback.adjustment_expiry_days)

    conn.execute(
        """INSERT INTO adjustment_rules
           (rule_id, user_id, indicator_id, adjustment_factor, reason, created_by, created_at, expires_at, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            rule_id,
            user_id,
            indicator_id,
            cfg.feedback.max_adjustment_factor,
            sanitize_comment(reason),
            analyst,
            now.isoformat(),
            expires_at.isoformat(),
        ),
    )

    log_audit_event(
        conn,
        actor=analyst,
        action="ADJUSTMENT_RULE_CREATED",
        details={
            "rule_id": rule_id,
            "user_id": user_id,
            "indicator_id": indicator_id,
            "expires_at": expires_at.isoformat(),
        },
    )

    return rule_id


def revoke_adjustment_rule(conn: sqlite3.Connection, rule_id: str, analyst: str) -> None:
    """Revoke an adjustment rule (sets is_active=0)."""
    conn.execute(
        "UPDATE adjustment_rules SET is_active = 0 WHERE rule_id = ?",
        (rule_id,),
    )
    conn.commit()
    log_audit_event(
        conn,
        actor=analyst,
        action="ADJUSTMENT_RULE_REVOKED",
        details={"rule_id": rule_id},
    )


def get_adjustment_factor(conn: sqlite3.Connection, user_id: str, indicator_id: str) -> float:
    """Get the active adjustment factor for a user+indicator combo. Returns 1.0 if none."""
    now = datetime.utcnow().isoformat()
    row = conn.execute(
        """SELECT adjustment_factor FROM adjustment_rules
           WHERE user_id = ? AND indicator_id = ? AND is_active = 1 AND expires_at > ?
           ORDER BY created_at DESC LIMIT 1""",
        (user_id, indicator_id, now),
    ).fetchone()
    return row[0] if row else 1.0


def expire_old_rules(conn: sqlite3.Connection) -> int:
    """Deactivate expired adjustment rules. Returns count deactivated."""
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "UPDATE adjustment_rules SET is_active = 0 WHERE is_active = 1 AND expires_at < ?",
        (now,),
    )
    conn.commit()
    return cursor.rowcount


def get_feedback_stats(conn: sqlite3.Connection) -> dict:
    """Get aggregate feedback statistics."""
    total = conn.execute("SELECT COUNT(*) FROM analyst_feedback").fetchone()[0]
    by_verdict: dict[str, int] = {}
    for row in conn.execute(
        "SELECT verdict, COUNT(*) FROM analyst_feedback GROUP BY verdict"
    ).fetchall():
        by_verdict[row[0]] = row[1]
    return {
        "total_reviewed": total,
        "by_verdict": by_verdict,
        "pct_benign": round(
            100
            * (by_verdict.get("benign_expected", 0) + by_verdict.get("false_positive", 0))
            / max(total, 1),
            1,
        ),
    }
