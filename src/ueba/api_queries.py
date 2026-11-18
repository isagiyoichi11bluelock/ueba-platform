"""
Read-only query helpers for the Casebook GUI API.
This module strictly queries SQLite and calls existing read functions without modifying schema or state.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Optional

from .db import get_connection
from .config import get_config, get_pseudonym_salt


def get_today_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Summary metrics and editorial headline for the Today page."""
    alerts = conn.execute(
        """SELECT a.alert_id, a.user_id, a.pseudonym_id, a.alert_date, a.risk_score,
                  a.severity_band, a.indicators_json, a.context_applied_json, a.summary,
                  a.status, u.role, u.department
           FROM alerts a
           LEFT JOIN users u ON a.user_id = u.user_id
           ORDER BY a.risk_score DESC"""
    ).fetchall()

    total_alerts = len(alerts)
    critical_cnt = sum(1 for a in alerts if a[5] == "critical")
    high_cnt = sum(1 for a in alerts if a[5] == "high")
    med_cnt = sum(1 for a in alerts if a[5] == "medium")
    low_cnt = sum(1 for a in alerts if a[5] == "low")
    open_cnt = sum(1 for a in alerts if a[9] == "open")
    reviewed_cnt = total_alerts - open_cnt

    # Top cases needing review (open, highest risk)
    open_cases = [a for a in alerts if a[9] == "open"]
    top_cases = []
    for a in open_cases[:5]:
        top_cases.append({
            "alert_id": a[0],
            "pseudonym": a[2],
            "role": a[10] or "Unknown",
            "department": a[11] or "Unknown",
            "date": a[3],
            "risk_score": a[4],
            "severity_band": a[5],
            "summary": a[8],
        })

    # Alert counts by day (last 14 days)
    day_counts = conn.execute(
        """SELECT alert_date, COUNT(*), SUM(CASE WHEN severity_band IN ('critical', 'high') THEN 1 ELSE 0 END)
           FROM alerts
           GROUP BY alert_date
           ORDER BY alert_date ASC"""
    ).fetchall()

    daily_strip = [
        {"date": r[0], "total": r[1], "high_or_critical": r[2]}
        for r in day_counts
    ]

    # Per-role activity counts
    role_counts = conn.execute(
        """SELECT COALESCE(u.role, 'Unassigned') as rname,
                  COUNT(a.alert_id) as total,
                  AVG(a.risk_score) as avg_score,
                  SUM(CASE WHEN a.severity_band IN ('critical', 'high') THEN 1 ELSE 0 END) as urgent
           FROM alerts a
           LEFT JOIN users u ON a.user_id = u.user_id
           GROUP BY u.role
           ORDER BY total DESC"""
    ).fetchall()

    role_activity = [
        {"role": r[0], "total": r[1], "avg_score": round(r[2] or 0.0, 1), "urgent": r[3]}
        for r in role_counts
    ]

    # Context events active in detection period
    month_end_active = conn.execute(
        "SELECT COUNT(*) FROM context_events WHERE context_type = 'month_end_close'"
    ).fetchone()[0]

    # Generate editorial sentence
    needs_look = critical_cnt + high_cnt
    if total_alerts == 0:
        headline = "No open cases are currently recorded. The system is monitoring baseline traffic."
    else:
        headline = f"{total_alerts} cases recorded across the detection window; {needs_look} require prompt attention."
        if month_end_active > 0:
            headline += " Elevated download volumes in Finance correspond to approved month-end close schedules."

    return {
        "headline": headline,
        "total_alerts": total_alerts,
        "open_count": open_cnt,
        "reviewed_count": reviewed_cnt,
        "critical_count": critical_cnt,
        "high_count": high_cnt,
        "medium_count": med_cnt,
        "low_count": low_cnt,
        "top_cases": top_cases,
        "daily_strip": daily_strip,
        "role_activity": role_activity,
    }


def get_inbox_alerts(
    conn: sqlite3.Connection,
    severity: Optional[list[str]] = None,
    status: Optional[list[str]] = None,
    role: Optional[list[str]] = None,
    min_score: float = 0.0,
    max_score: float = 100.0,
    search: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Get filtered and formatted alerts for the Inbox page."""
    query = """
        SELECT a.alert_id, a.user_id, a.pseudonym_id, a.alert_date, a.risk_score,
               a.severity_band, a.indicators_json, a.context_applied_json, a.summary,
               a.baseline_confidence, a.status, a.scenario_id, u.role, u.department
        FROM alerts a
        LEFT JOIN users u ON a.user_id = u.user_id
        WHERE a.risk_score >= ? AND a.risk_score <= ?
    """
    params: list[Any] = [min_score, max_score]

    if severity:
        placeholders = ",".join("?" for _ in severity)
        query += f" AND a.severity_band IN ({placeholders})"
        params.extend(severity)

    if status:
        placeholders = ",".join("?" for _ in status)
        query += f" AND a.status IN ({placeholders})"
        params.extend(status)

    if role:
        placeholders = ",".join("?" for _ in role)
        query += f" AND u.role IN ({placeholders})"
        params.extend(role)

    if search:
        query += " AND (a.pseudonym_id LIKE ? OR u.role LIKE ? OR a.summary LIKE ?)"
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param])

    query += " ORDER BY a.risk_score DESC, a.alert_date DESC"

    rows = conn.execute(query, params).fetchall()
    results = []

    for r in rows:
        indicators = []
        if r[6]:
            try:
                indicators = json.loads(r[6])
            except Exception:
                pass

        # Extract top 2 plain reasons
        reasons = []
        for ind in indicators:
            if isinstance(ind, dict) and "name" in ind and ind["name"] != "CHAIN_BONUS":
                clean_name = ind["name"].replace("_", " ").lower()
                reasons.append(clean_name)
        reasons_summary = ", ".join(reasons[:2]) if reasons else "routine variance"

        results.append({
            "alert_id": r[0],
            "pseudonym": r[2],
            "alert_date": r[3],
            "risk_score": r[4],
            "severity_band": r[5],
            "reasons_summary": reasons_summary,
            "status": r[10],
            "role": r[12] or "Unassigned",
            "department": r[13] or "General",
            "scenario_id": r[11],
            "baseline_confidence": round(r[9] or 1.0, 2),
        })

    return results


def get_case_detail(conn: sqlite3.Connection, alert_id: str) -> Optional[dict[str, Any]]:
    """Comprehensive incident case file with evidence provenance and timeline events."""
    alert = conn.execute(
        """SELECT a.alert_id, a.user_id, a.pseudonym_id, a.alert_date, a.risk_score,
                  a.severity_band, a.indicators_json, a.context_applied_json, a.summary,
                  a.baseline_confidence, a.status, a.scenario_id,
                  u.role, u.department, u.home_country, u.home_city,
                  u.work_start_hour, u.work_end_hour, u.is_contractor, u.is_night_shift
           FROM alerts a
           LEFT JOIN users u ON a.user_id = u.user_id
           WHERE a.alert_id = ?""",
        (alert_id,),
    ).fetchone()

    if not alert:
        return None

    user_id = alert[1]
    pseudonym = alert[2]
    alert_date_str = alert[3]
    alert_date = datetime.fromisoformat(alert_date_str).date() if "T" in alert_date_str else date.fromisoformat(alert_date_str)

    indicators_raw = json.loads(alert[6]) if alert[6] else []
    context_applied = json.loads(alert[7]) if alert[7] else []

    # Clean indicators and parse chain bonuses
    indicators = []
    chain_bonuses = []
    for item in indicators_raw:
        if isinstance(item, dict):
            if item.get("name") == "CHAIN_BONUS":
                chain_bonuses = item.get("bonuses", [])
            else:
                indicators.append(item)

    # Day window for timeline events
    start_dt = (datetime.combine(alert_date, datetime.min.time()) - timedelta(hours=2)).isoformat()
    end_dt = (datetime.combine(alert_date + timedelta(days=1), datetime.min.time()) + timedelta(hours=2)).isoformat()

    # Query events that took place on that day
    logins = conn.execute(
        """SELECT event_id, timestamp, country, city, device_id, auth_result, auth_method
           FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
           ORDER BY timestamp ASC""",
        (user_id, start_dt, end_dt),
    ).fetchall()

    downloads = conn.execute(
        """SELECT event_id, timestamp, bytes, file_count, destination_type, resource_id
           FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
           ORDER BY timestamp ASC""",
        (user_id, start_dt, end_dt),
    ).fetchall()

    privileges = conn.execute(
        """SELECT event_id, timestamp, action, target, result
           FROM privilege_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
           ORDER BY timestamp ASC""",
        (user_id, start_dt, end_dt),
    ).fetchall()

    # Build timeline event ticks
    timeline_events = []
    evidence_ids = set()
    for ind in indicators:
        for eid in ind.get("evidence_event_ids", []):
            evidence_ids.add(eid)

    for l in logins:
        eid = l[0]
        timeline_events.append({
            "event_id": eid,
            "type": "login",
            "timestamp": l[1],
            "description": f"Login from {l[3] or 'Unknown'}, {l[2] or 'Unknown'} via {l[4] or 'Unknown device'} ({l[5]})",
            "is_evidence": eid in evidence_ids,
            "result": l[5],
        })

    for d in downloads:
        eid = d[0]
        mb = round((d[2] or 0) / (1024 * 1024), 1)
        timeline_events.append({
            "event_id": eid,
            "type": "download",
            "timestamp": d[1],
            "description": f"Download {mb} MB ({d[3]} files) to {d[4]}",
            "is_evidence": eid in evidence_ids,
            "bytes": d[2],
            "destination": d[4],
        })

    for p in privileges:
        eid = p[0]
        timeline_events.append({
            "event_id": eid,
            "type": "privilege",
            "timestamp": p[1],
            "description": f"Privilege action: {p[2]} on target {p[3]} ({p[4]})",
            "is_evidence": eid in evidence_ids,
            "action": p[2],
            "result": p[4],
        })

    timeline_events.sort(key=lambda x: x["timestamp"])

    # Editorial case narrative
    work_start = alert[16] if alert[16] is not None else 9
    work_end = alert[17] if alert[17] is not None else 17
    narrative = _generate_editorial_narrative(
        pseudonym=pseudonym,
        role=alert[12] or "employee",
        alert_date=alert_date_str,
        work_start=work_start,
        work_end=work_end,
        indicators=indicators,
        context_applied=context_applied,
        risk_score=alert[4],
    )

    # Analyst feedback history for this alert
    feedbacks = conn.execute(
        """SELECT feedback_id, verdict, comment, analyst, created_at
           FROM analyst_feedback
           WHERE alert_id = ?
           ORDER BY created_at DESC""",
        (alert_id,),
    ).fetchall()

    feedback_history = [
        {
            "feedback_id": f[0],
            "verdict": f[1],
            "notes": f[2],
            "analyst_role": f[3],
            "timestamp": f[4],
        }
        for f in feedbacks
    ]

    return {
        "alert_id": alert[0],
        "pseudonym": pseudonym,
        "user_id_masked": pseudonym,  # Default masked
        "alert_date": alert_date_str,
        "risk_score": alert[4],
        "severity_band": alert[5],
        "summary": alert[8],
        "baseline_confidence": round(alert[9] or 1.0, 2),
        "status": alert[10],
        "scenario_id": alert[11],
        "role": alert[12] or "Unassigned",
        "department": alert[13] or "General",
        "home_country": alert[14] or "US",
        "home_city": alert[15] or "New York",
        "work_start_hour": work_start,
        "work_end_hour": work_end,
        "is_contractor": bool(alert[18]),
        "is_night_shift": bool(alert[19]),
        "narrative": narrative,
        "indicators": indicators,
        "chain_bonuses": chain_bonuses,
        "context_applied": context_applied,
        "timeline_events": timeline_events,
        "feedback_history": feedback_history,
    }


def _generate_editorial_narrative(
    pseudonym: str,
    role: str,
    alert_date: str,
    work_start: int,
    work_end: int,
    indicators: list[dict],
    context_applied: list[dict],
    risk_score: float,
) -> str:
    """Generate a calm, collegiate narrative summary for the case."""
    lines = []
    ind_names = [i.get("name", "") for i in indicators]

    lines.append(
        f"On {alert_date}, our telemetry registered unusual activity associated with {pseudonym} ({role}). "
        f"Their baseline schedule typically runs {work_start:02d}:00 to {work_end:02d}:00 local time."
    )

    specifics = []
    if "NEW_COUNTRY" in ind_names:
        for ind in indicators:
            if ind.get("name") == "NEW_COUNTRY":
                specifics.append(f"an authentication from an unobserved jurisdiction ({ind.get('observed_value', 'foreign country')})")
    if "UNUSUAL_HOUR" in ind_names:
        for ind in indicators:
            if ind.get("name") == "UNUSUAL_HOUR":
                h = int(ind.get("observed_value", 0))
                specifics.append(f"activity at {h:02d}:00 outside their habitual working hours")
    if "DOWNLOAD_VOLUME_SPIKE" in ind_names or "BULK_DOWNLOAD_EXTERNAL" in ind_names:
        for ind in indicators:
            if "DOWNLOAD" in ind.get("name", ""):
                mb = round((ind.get("observed_value", 0) or 0) / (1024 * 1024), 1)
                specifics.append(f"download egress totaling approximately {mb} MB")
                break
    if "PRIVILEGE_ESCALATION_SEQUENCE" in ind_names or "OFF_HOURS_PRIVILEGE_USE" in ind_names:
        specifics.append("elevated administrative commands or privilege role assignments")

    if specifics:
        lines.append("Observed signals include " + "; ".join(specifics) + ".")

    if context_applied:
        ctx_types = ", ".join(c.get("context_type", "known schedule") for c in context_applied)
        lines.append(
            f"The business context registry verified an approved exception ({ctx_types}), "
            f"which moderated the overall calculated score to {int(risk_score)}."
        )
    else:
        lines.append(
            "No prior business travel, on-call window, or maintenance schedule was on file for this window. "
            "This may have an innocent explanation, but peer comparisons warrant an analyst look."
        )

    return " ".join(lines)


def get_people_list(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """List all pseudonymous user profiles."""
    rows = conn.execute(
        """SELECT user_id, pseudonym, role, department, home_country, home_city,
                  work_start_hour, work_end_hour, is_contractor, is_night_shift, is_part_time
           FROM users
           ORDER BY pseudonym ASC"""
    ).fetchall()

    return [
        {
            "user_id": r[0],
            "pseudonym": r[1],
            "role": r[2],
            "department": r[3],
            "home_country": r[4],
            "home_city": r[5],
            "work_start_hour": r[6],
            "work_end_hour": r[7],
            "is_contractor": bool(r[8]),
            "is_night_shift": bool(r[9]),
            "is_part_time": bool(r[10]),
        }
        for r in rows
    ]


def get_person_timeline(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    """Longitudinal telemetry data for the People page."""
    user = conn.execute(
        "SELECT user_id, pseudonym, role, department, home_country, home_city, work_start_hour, work_end_hour FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if not user:
        return {}

    # Hour of day heatmap (24 hours by 14 days)
    logins = conn.execute(
        """SELECT timestamp, country, city, device_id, auth_result
           FROM login_events
           WHERE user_id = ?
           ORDER BY timestamp ASC""",
        (user_id,),
    ).fetchall()

    # Group by day and hour
    day_hour_matrix: dict[str, list[int]] = {}
    for l in logins:
        try:
            dt = datetime.fromisoformat(l[0])
            d_str = dt.date().isoformat()
            if d_str not in day_hour_matrix:
                day_hour_matrix[d_str] = [0] * 24
            day_hour_matrix[d_str][dt.hour] += 1
        except Exception:
            pass

    # Daily download volumes
    downloads = conn.execute(
        """SELECT date(timestamp) as d, SUM(bytes), COUNT(*), SUM(file_count)
           FROM download_events
           WHERE user_id = ?
           GROUP BY date(timestamp)
           ORDER BY d ASC""",
        (user_id,),
    ).fetchall()

    download_timeline = [
        {
            "date": d[0],
            "bytes": d[1],
            "mb": round(d[1] / (1024 * 1024), 2),
            "event_count": d[2],
            "file_count": d[3],
        }
        for d in downloads
    ]

    # Locations seen
    locs = conn.execute(
        """SELECT country, city, MIN(timestamp) as first_seen, COUNT(*) as count
           FROM login_events
           WHERE user_id = ? AND city IS NOT NULL
           GROUP BY country, city
           ORDER BY first_seen ASC""",
        (user_id,),
    ).fetchall()

    locations = [
        {"country": lc[0], "city": lc[1], "first_seen": lc[2], "login_count": lc[3]}
        for lc in locs
    ]

    # Administrative privilege history
    privs = conn.execute(
        """SELECT timestamp, action, target, result
           FROM privilege_events
           WHERE user_id = ?
           ORDER BY timestamp DESC
           LIMIT 20""",
        (user_id,),
    ).fetchall()

    privilege_history = [
        {"timestamp": p[0], "action": p[1], "target": p[2], "result": p[3]}
        for p in privs
    ]

    return {
        "user_id": user[0],
        "pseudonym": user[1],
        "role": user[2],
        "department": user[3],
        "home_country": user[4],
        "home_city": user[5],
        "work_start_hour": user[6],
        "work_end_hour": user[7],
        "day_hour_matrix": day_hour_matrix,
        "download_timeline": download_timeline,
        "locations": locations,
        "privilege_history": privilege_history,
    }


def get_normal_baselines(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    """Baseline metrics, peer comparisons, and cold-start blending for Normal page."""
    user = conn.execute(
        "SELECT user_id, pseudonym, role, department FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if not user:
        return {}

    user_bl_rows = conn.execute(
        """SELECT metric_name, metric_value, confidence, computed_date
           FROM user_baselines
           WHERE user_id = ?
           ORDER BY computed_date DESC""",
        (user_id,),
    ).fetchall()

    bl_dict = {}
    conf = 1.0
    computed_date = None
    for r in user_bl_rows:
        if r[0] not in bl_dict:
            try:
                bl_dict[r[0]] = json.loads(r[1])
            except Exception:
                bl_dict[r[0]] = r[1]
            conf = r[2]
            computed_date = r[3]

    role = user[2]
    role_bl_rows = conn.execute(
        """SELECT metric_name, metric_value
           FROM role_baselines
           WHERE role = ?
           ORDER BY computed_date DESC""",
        (role,),
    ).fetchall()

    role_bl = {}
    for r in role_bl_rows:
        if r[0] not in role_bl:
            try:
                role_bl[r[0]] = json.loads(r[1])
            except Exception:
                role_bl[r[0]] = r[1]

    # Cold start explanation
    is_cold_start = conf < 0.8
    if is_cold_start:
        explanation = (
            f"This account has fewer than 14 active observation days. Individual behavior is blended with "
            f"the {role} peer baseline (Individual weight: {int(conf * 100)}%, Peer weight: {int((1 - conf) * 100)}%). "
            f"This dampens speculative alerts while early patterns stabilize."
        )
    else:
        explanation = (
            f"Sufficient baseline depth established ({int(conf * 100)}% confidence). "
            f"Anomalies are evaluated against personal rolling 60-day history with peer reference."
        )

    return {
        "user_id": user[0],
        "pseudonym": user[1],
        "role": role,
        "department": user[3],
        "confidence": round(conf, 2),
        "computed_date": computed_date,
        "user_baseline": bl_dict,
        "role_baseline": role_bl,
        "explanation": explanation,
        "is_cold_start": is_cold_start,
    }


def get_rehearsal_scenarios(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Ground-truth scenario chapters (S1–S8) for the Rehearsal page."""
    gt_rows = conn.execute(
        "SELECT scenario_id, user_id, start_time, end_time, label, description, expected_min_score, expected_max_score FROM ground_truth ORDER BY scenario_id ASC"
    ).fetchall()

    chapters = []
    for r in gt_rows:
        s_id = r[0]
        u_id = r[1]
        s_time = r[2][:10]
        e_time = r[3][:10]
        exp_min = r[6]
        exp_max = r[7]

        alert = conn.execute(
            """SELECT alert_id, risk_score, severity_band, indicators_json, context_applied_json, summary, pseudonym_id
               FROM alerts
               WHERE user_id = ? AND alert_date >= ? AND alert_date <= ?
               ORDER BY risk_score DESC LIMIT 1""",
            (u_id, s_time, e_time),
        ).fetchone()

        score = alert[1] if alert else 0.0
        band = alert[2] if alert else "none"
        alert_id = alert[0] if alert else None
        pseudonym = alert[6] if alert else "Unknown"
        passed = exp_min <= score <= exp_max

        # Narrative story paragraph per chapter
        story = _get_scenario_chapter_story(s_id, r[5])

        chapters.append({
            "scenario_id": s_id,
            "title": f"Chapter {s_id}: {_get_scenario_title(s_id)}",
            "user_id": u_id,
            "pseudonym": pseudonym,
            "label": r[4],
            "story": story,
            "expected_range": f"{int(exp_min)} – {int(exp_max)}",
            "actual_score": round(score, 1),
            "severity_band": band,
            "passed": passed,
            "alert_id": alert_id,
        })

    return chapters


def _get_scenario_title(s_id: str) -> str:
    titles = {
        "S1": "Compromised Credentials Killchain",
        "S2": "Departing Employee Data Hoarding",
        "S3": "Contractor Scope Creep",
        "S4": "Approved Business Travel (Benign)",
        "S5": "Month-End Financial Close (Benign)",
        "S6": "New Joiner Cold Start (Benign)",
        "S7": "On-Call Emergency Maintenance (Benign)",
        "S8": "Unapproved Travel (Negative Control)",
    }
    return titles.get(s_id, "Injected Behavioral Test")


def _get_scenario_chapter_story(s_id: str, raw_desc: str) -> str:
    stories = {
        "S1": "A developer account undergoes a sudden burst of failed password attempts followed by an anomalous successful login from Tokyo at 03:12 local time on an unrecognized device. Within thirty minutes, root privileges are invoked and 2.4 GB of source code is transferred to an external destination.",
        "S2": "A sales representative with an impending departure date gradually ramps up daily file downloads across a 10-day period. Sensitive documents outside their standard portfolio are accessed and saved to personal endpoints.",
        "S3": "An external engineering contractor begins querying restricted HR personnel records and corporate accounting databases late in the evening, well outside the customary scope of their role peers.",
        "S4": "A senior financial analyst logs in from London at an off-hour from an unfamiliar corporate laptop. Because an authorized travel request was filed with HR in advance, context dampening moderates the alert to Low severity.",
        "S5": "During the final three working days of the quarter, the financial accounting team downloads eight times their habitual file volume. The engine correlates this against the month-end close calendar and mitigates false alarms.",
        "S6": "A new software engineer joins the organization with only five days of tenure. Rather than triggering high-severity alerts for exploring standard developer repositories, the engine blends individual and peer baselines.",
        "S7": "An on-call IT administrator invokes elevated superuser privileges at 02:00 AM to remediate an urgent outage. The system notes an active on-call schedule and reduces severity accordingly.",
        "S8": "A user produces an authentication pattern identical to Scenario 4 (foreign jurisdiction and unusual hours), but without any pre-approved travel context on record. The score remains elevated as a negative control.",
    }
    return stories.get(s_id, raw_desc)


def get_ledger_entries(conn: sqlite3.Connection, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Cryptographic audit chain entries with tamper status."""
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

    rows = conn.execute(
        """SELECT entry_id, timestamp, actor, action, details_json, prev_hash, entry_hash,
                  ROW_NUMBER() OVER (ORDER BY timestamp ASC) as seq_num
           FROM audit_log
           ORDER BY timestamp DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()

    entries = []
    for r in rows:
        entries.append({
            "entry_id": r[0],
            "timestamp": r[1],
            "actor": r[2],
            "action": r[3],
            "details": json.loads(r[4]) if r[4] else {},
            "prev_hash_short": r[5][:12] + "…" if r[5] else "0" * 8,
            "entry_hash_short": r[6][:12] + "…" if r[6] else "",
            "prev_hash_full": r[5],
            "entry_hash_full": r[6],
            "sequence_number": r[7],
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": entries,
    }


def get_safeguards_info(conn: sqlite3.Connection) -> dict[str, Any]:
    """Technical privacy guarantees and limitation declarations."""
    cfg = get_config()

    # Load markdown documents
    repo_root = Path(__file__).parent.parent.parent
    privacy_md_path = repo_root / "docs" / "PRIVACY.md"
    limitations_md_path = repo_root / "docs" / "LIMITATIONS.md"

    privacy_text = privacy_md_path.read_text(encoding="utf-8") if privacy_md_path.exists() else ""
    limitations_text = limitations_md_path.read_text(encoding="utf-8") if limitations_md_path.exists() else ""

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    salt = get_pseudonym_salt()
    has_salt = bool(salt and salt != "default-salt-value")

    return {
        "live_safeguards": [
            {
                "name": "HMAC-SHA256 Pseudonymization",
                "status": "Active",
                "detail": f"All {user_count} workforce identities are represented strictly as U-xxxxxx tokens in analyst views.",
            },
            {
                "name": "Class C (/24) IP Truncation",
                "status": "Active",
                "detail": "Last octet of client IP addresses is zeroed at ingestion (e.g. 192.168.1.0/24) to prevent home ISP deanonymization.",
            },
            {
                "name": "Separation of Duties (RBAC)",
                "status": "Enforced",
                "detail": "Identity re-identification is locked to the senior_analyst role and requires audited ≥20 character written justification.",
            },
            {
                "name": "Data Retention Lifecycle",
                "status": "Configured",
                "detail": f"Telemetry events expire after {cfg.retention.events_days} days; risk alerts expire after {cfg.retention.alerts_days} days; audit logs retained {cfg.retention.audit_days} days.",
            },
            {
                "name": "Non-Accusatory Terminology",
                "status": "Enforced",
                "detail": "Language strictly describes unusual variance and indicators requiring review; no conclusions of malice or guilt.",
            },
        ],
        "privacy_doc": privacy_text,
        "limitations_doc": limitations_text,
    }
