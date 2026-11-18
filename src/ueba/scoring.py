"""Risk scoring: combine indicators into 0-100 score with explanation."""
from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import date, datetime
from typing import Any
from .config import get_config, load_scoring_weights


def _diminishing_returns_score(points: list[float]) -> float:
    """
    Combine indicator points using diminishing-returns formula:
    score = 100 * (1 - prod(1 - p_i/100))
    So many weak indicators don't trivially saturate.
    """
    if not points:
        return 0.0
    result = 1.0
    for p in points:
        p_clamped = max(0.0, min(95.0, float(p)))
        result *= (1.0 - p_clamped / 100.0)
    return max(0.0, min(100.0, 100.0 * (1.0 - result)))


def _get_severity_band(score: float) -> str:
    """Map score to severity band."""
    cfg = get_config()
    bands = cfg.scoring.bands
    if score <= bands.low[1]:
        return "low"
    elif score <= bands.medium[1]:
        return "medium"
    elif score <= bands.high[1]:
        return "high"
    else:
        return "critical"


def _apply_chain_bonuses(indicators: list[dict], base_score: float) -> tuple[float, list[str]]:
    """Apply chain bonuses for dangerous indicator combinations."""
    cfg = get_config()
    bonuses_applied = []
    bonus_total = 0.0

    names = {ind["name"] for ind in indicators}

    # new_country + unusual_hour + bulk_download within 24h
    if "NEW_COUNTRY" in names and "UNUSUAL_HOUR" in names and "DOWNLOAD_VOLUME_SPIKE" in names:
        b = cfg.scoring.chain_bonus.get("new_country_unusual_hour_bulk_download", 15)
        bonus_total += b
        bonuses_applied.append(f"Chain bonus: new location + off-hours + bulk download (+{b} pts)")

    # failed_login_burst + privilege escalation
    if "FAILED_LOGIN_BURST_THEN_SUCCESS" in names and "PRIVILEGE_ESCALATION_SEQUENCE" in names:
        b = cfg.scoring.chain_bonus.get("failed_login_then_privilege", 10)
        bonus_total += b
        bonuses_applied.append(f"Chain bonus: credential attack + privilege escalation (+{b} pts)")

    # new_device + new_country
    if "NEW_DEVICE" in names and "NEW_COUNTRY" in names:
        b = cfg.scoring.chain_bonus.get("new_device_new_country", 8)
        bonus_total += b
        bonuses_applied.append(f"Chain bonus: new device + new location (+{b} pts)")

    final_score = min(100.0, base_score + bonus_total)
    return final_score, bonuses_applied


def _generate_summary(user_pseudonym: str, score: float, band: str, indicators: list[dict], context_applied: list[dict]) -> str:
    """Generate a 2-4 sentence plain-English summary."""
    top = sorted(indicators, key=lambda x: x.get("severity_points", 0), reverse=True)[:3]
    indicator_desc = "; ".join(
        f"{ind['name'].replace('_', ' ').lower()} (event: {ind['evidence_event_ids'][0] if ind.get('evidence_event_ids') else 'N/A'})"
        for ind in top
    )

    summary = f"Risk {int(score)} ({band.upper()}). "
    if top:
        summary += f"{len(indicators)} indicator(s) flagged: {indicator_desc}. "
    if context_applied:
        ctx_names = ", ".join(c.get("context_type", "unknown") for c in context_applied)
        summary += f"Context applied ({ctx_names}) reduced the score. "
    summary += "This is unusual behavior and may have a legitimate explanation; analyst review is recommended. An anomaly is not proof of wrongdoing."
    return summary


def compute_risk_score(
    user_id: str,
    pseudonym_id: str,
    alert_date: date,
    indicators: list[dict],
    context_applied: list[dict],
    baseline_confidence: float,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """
    Compute risk score and save alert to DB.
    Returns the alert dict.
    """
    # Apply analyst adjustment rules
    from .feedback import get_adjustment_factor
    adjusted_indicators = []
    for ind in indicators:
        adj_factor = get_adjustment_factor(conn, user_id, ind["name"])
        adjusted_points = ind["severity_points"] * adj_factor
        adjusted_ind = dict(ind)
        adjusted_ind["severity_points"] = adjusted_points
        adjusted_ind["adjustment_applied"] = adj_factor < 1.0
        adjusted_indicators.append(adjusted_ind)

    # Calculate score with diminishing returns
    points = [ind["severity_points"] for ind in adjusted_indicators]
    base_score = _diminishing_returns_score(points)

    # Apply chain bonuses
    final_score, chain_bonuses = _apply_chain_bonuses(adjusted_indicators, base_score)

    band = _get_severity_band(final_score)
    summary = _generate_summary(pseudonym_id, final_score, band, adjusted_indicators, context_applied)

    alert_id = str(uuid.uuid4())
    all_inds_to_store = adjusted_indicators + ([{"name": "CHAIN_BONUS", "bonuses": chain_bonuses}] if chain_bonuses else [])

    conn.execute(
        """INSERT INTO alerts 
           (alert_id, user_id, pseudonym_id, alert_date, risk_score, severity_band,
            indicators_json, context_applied_json, summary, baseline_confidence, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
        (alert_id, user_id, pseudonym_id, alert_date.isoformat(),
         round(final_score, 2), band,
         json.dumps(all_inds_to_store),
         json.dumps(context_applied),
         summary, baseline_confidence)
    )
    conn.commit()

    return {
        "alert_id": alert_id,
        "user_id": user_id,
        "pseudonym_id": pseudonym_id,
        "alert_date": alert_date.isoformat(),
        "risk_score": round(final_score, 2),
        "severity_band": band,
        "indicators": adjusted_indicators,
        "chain_bonuses": chain_bonuses,
        "context_applied": context_applied,
        "summary": summary,
        "baseline_confidence": baseline_confidence,
    }
