"""Evaluation against ground truth scenarios."""
from __future__ import annotations
import sqlite3
from typing import Any


def evaluate_against_ground_truth(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Compare alert scores against ground truth labels.
    Returns precision, recall, F1, per-scenario results, confusion matrix values.
    """
    cfg_rows = conn.execute("SELECT * FROM ground_truth").fetchall()
    if not cfg_rows:
        return {"error": "No ground truth data found"}

    results = []
    for gt in cfg_rows:
        scenario_id = gt[0]
        user_id = gt[1]
        start_time = gt[2][:10]
        end_time = gt[3][:10]
        label = gt[4]
        expected_min = gt[6]
        expected_max = gt[7]

        # Find best alert for this user in the scenario window
        alert_row = conn.execute(
            """SELECT alert_id, risk_score, severity_band, summary
               FROM alerts
               WHERE user_id = ? AND alert_date >= ? AND alert_date <= ?
               ORDER BY risk_score DESC LIMIT 1""",
            (user_id, start_time, end_time)
        ).fetchone()

        if alert_row:
            actual_score = alert_row[1]
            alert_id = alert_row[0]
            severity_band = alert_row[2]
        else:
            actual_score = 0.0
            alert_id = None
            severity_band = "none"

        # Determine predicted class (threshold 55 for malicious classification)
        THRESHOLD = 55.0
        predicted_malicious = actual_score >= THRESHOLD
        actually_malicious = label in ("malicious_or_compromised", "TRUE_POSITIVE", "malicious")

        in_expected_range = expected_min <= actual_score <= expected_max

        results.append({
            "scenario_id": scenario_id,
            "label": label,
            "expected_min": expected_min,
            "expected_max": expected_max,
            "actual_score": actual_score,
            "severity_band": severity_band,
            "alert_id": alert_id,
            "in_expected_range": in_expected_range,
            "predicted_malicious": predicted_malicious,
            "actually_malicious": actually_malicious,
            "tp": int(predicted_malicious and actually_malicious),
            "fp": int(predicted_malicious and not actually_malicious),
            "tn": int(not predicted_malicious and not actually_malicious),
            "fn": int(not predicted_malicious and actually_malicious),
        })

    # Aggregate metrics
    tp = sum(r["tp"] for r in results)
    fp = sum(r["fp"] for r in results)
    tn = sum(r["tn"] for r in results)
    fn = sum(r["fn"] for r in results)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    fpr = fp / max(fp + tn, 1)

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "false_positive_rate": round(fpr, 3),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "per_scenario": results,
        "scenarios_in_expected_range": sum(1 for r in results if r["in_expected_range"]),
        "total_scenarios": len(results),
    }


# Backward compatibility alias
evaluate_pipeline = evaluate_against_ground_truth
