"""Context-aware risk dampening: benign exception handling."""
from __future__ import annotations
import sqlite3
from datetime import datetime, date
from typing import Any
from .config import get_config


def get_active_contexts(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
) -> list[dict]:
    """Get all context events active on target_date for user."""
    day_start = datetime.combine(target_date, datetime.min.time()).isoformat()
    day_end = datetime.combine(target_date, datetime.max.time().replace(microsecond=0)).isoformat()

    rows = conn.execute(
        """SELECT context_id, context_type, start_time, end_time, approved_by_role, notes
           FROM context_events
           WHERE user_id = ? AND start_time <= ? AND end_time >= ?""",
        (user_id, day_end, day_start)
    ).fetchall()

    return [
        {
            "context_id": r[0],
            "context_type": r[1],
            "start_time": r[2],
            "end_time": r[3],
            "approved_by_role": r[4],
            "notes": r[5],
        }
        for r in rows
    ]


INDICATOR_CONTEXT_MAP = {
    "approved_travel": ["NEW_COUNTRY", "NEW_CITY", "UNUSUAL_HOUR", "NEW_DEVICE", "ML_ANOMALY_SUPPORT"],
    "month_end_close": ["DOWNLOAD_VOLUME_SPIKE", "DOWNLOAD_TREND", "UNUSUAL_HOUR", "PEER_DEVIATION", "ML_ANOMALY_SUPPORT"],
    "on_call": ["OFF_HOURS_PRIVILEGE_USE", "UNUSUAL_HOUR", "PRIVILEGE_ESCALATION_SEQUENCE", "ML_ANOMALY_SUPPORT"],
    "project_deadline": ["UNUSUAL_HOUR", "DOWNLOAD_VOLUME_SPIKE", "ML_ANOMALY_SUPPORT"],
    "new_joiner": ["NEW_RESOURCE_ACCESS", "PEER_DEVIATION", "OUT_OF_ROLE_SENSITIVE_ACCESS", "ML_ANOMALY_SUPPORT", "UNUSUAL_HOUR"],
    "role_change": ["OUT_OF_ROLE_SENSITIVE_ACCESS", "NEW_RESOURCE_ACCESS", "ML_ANOMALY_SUPPORT"],
}


def apply_context_dampening(
    indicators: list[dict],
    contexts: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Apply context dampening to indicators.
    Returns (dampened_indicators, applied_context_records).

    Dampening NEVER silently removes an alert:
    - Lowers score but keeps indicator visible with 'context applied' tag
    - Caps maximum reduction at config max_reduction_factor
    - Some indicators are undampenable (e.g., IMPOSSIBLE_TRAVEL, FAILED_LOGIN_BURST_THEN_SUCCESS)
    """
    cfg = get_config()
    undampenable = set(cfg.context_dampening.undampenable_indicators)

    dampened = []
    applied_contexts = []

    for ind in indicators:
        indicator_name = ind["name"]

        if indicator_name in undampenable:
            # Cannot be dampened
            dampened.append(dict(ind) | {"context_dampened": False, "dampening_note": "Undampenable indicator"})
            continue

        best_reduction = 0.0
        best_context = None

        for ctx in contexts:
            ctx_type = ctx["context_type"]
            applicable_indicators = INDICATOR_CONTEXT_MAP.get(ctx_type, [])

            if indicator_name in applicable_indicators:
                reduction_factor = getattr(cfg.context_dampening, ctx_type, 0.0)
                if reduction_factor > best_reduction:
                    best_reduction = reduction_factor
                    best_context = ctx

        if best_context and best_reduction > 0:
            # Cap reduction
            capped_reduction = min(best_reduction, cfg.context_dampening.max_reduction_factor)
            original_points = ind["severity_points"]
            new_points = original_points * (1.0 - capped_reduction)

            dampened_ind = dict(ind)
            dampened_ind["severity_points"] = new_points
            dampened_ind["context_dampened"] = True
            dampened_ind["original_severity_points"] = original_points
            dampened_ind["dampening_reduction"] = capped_reduction
            dampened_ind["dampening_context"] = best_context["context_type"]
            dampened_ind["dampening_note"] = (
                f"Score reduced by {int(capped_reduction * 100)}% due to {best_context['context_type']} "
                f"context (approved by {best_context['approved_by_role']}). "
                f"Original: {original_points:.1f} pts, After dampening: {new_points:.1f} pts."
            )
            dampened.append(dampened_ind)

            applied_contexts.append({
                "context_type": best_context["context_type"],
                "indicator": indicator_name,
                "reduction_factor": capped_reduction,
                "original_points": original_points,
                "dampened_points": new_points,
                "context_id": best_context["context_id"],
                "approved_by": best_context["approved_by_role"],
            })
        else:
            dampened.append(dict(ind) | {"context_dampened": False})

    return dampened, applied_contexts


# Backward compatibility alias
apply_dampening = apply_context_dampening
