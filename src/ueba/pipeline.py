"""End-to-end pipeline orchestration."""
from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from .config import get_config, load_scoring_weights
from .db import get_connection, get_db_path
from .baseline import compute_user_baseline, compute_role_baseline, blend_baselines, save_baseline_to_db
from .indicators import compute_indicators
from .ml_signal import compute_ml_anomaly_score
from .scoring import compute_risk_score
from .context_dampening import get_active_contexts, apply_context_dampening
from .privacy import get_pseudonym
from .audit import log_audit_event
from .evaluate import evaluate_against_ground_truth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(conn=None, close_conn: bool = True) -> dict:
    """
    Run the full analytics pipeline:
    1. For each user and each day in detection period:
       a. Compute rolling baseline (using only prior data - zero leakage)
       b. Blend with role baseline
       c. Compute indicators
       d. Apply ML anomaly signal
       e. Apply context dampening
       f. Score and save alert (if score >= MIN_SCORE_TO_SAVE)
    2. Evaluate against ground truth
    3. Return summary
    """
    cfg = get_config()
    weights = load_scoring_weights()

    if conn is None:
        conn = get_connection()

    end_date = cfg.get_end_date()
    start_date = cfg.get_start_date()
    detection_start = start_date + timedelta(days=cfg.data.detection_start_day - 1)

    logger.info(f"Pipeline: detection period {detection_start} to {end_date}")

    # Clear existing alerts and baselines
    conn.execute("DELETE FROM alerts")
    conn.execute("DELETE FROM user_baselines")
    conn.commit()

    # Get all users
    users = conn.execute("SELECT user_id, role, pseudonym FROM users").fetchall()
    logger.info(f"Processing {len(users)} users across {(end_date - detection_start).days + 1} detection days")

    alerts_created = 0
    MIN_SCORE_TO_SAVE = 18.0  # Captures low severity alerts including benign exceptions

    # Pre-cache role baselines per date
    role_baselines_cache: dict[tuple[str, str], dict] = {}

    current_date = detection_start
    while current_date <= end_date:
        date_str = current_date.isoformat()
        
        # Compute role baselines for this date
        roles = {u[1] for u in users}
        for r in roles:
            role_baselines_cache[(r, date_str)] = compute_role_baseline(conn, r, current_date)

        for user_row in users:
            user_id, role, pseudonym_id = user_row[0], user_row[1], user_row[2]

            try:
                # 1. Compute baselines (no data leakage: only events before current_date)
                user_bl = compute_user_baseline(conn, user_id, current_date)
                role_bl = role_baselines_cache.get((role, date_str), {})
                confidence = user_bl.get("confidence", 0.5)
                blended_bl = blend_baselines(user_bl, role_bl, confidence)

                # Save baseline
                save_baseline_to_db(conn, user_id, current_date, user_bl, baseline_type="user")

                # 2. Compute rule-based indicators
                indicators = compute_indicators(conn, user_id, current_date, blended_bl, role_bl)

                # 3. Add supporting ML signal
                ml_indicator = compute_ml_anomaly_score(conn, user_id, current_date, current_date, weights)
                if ml_indicator:
                    indicators.append(ml_indicator)

                if not indicators:
                    continue

                # 4. Context dampening
                contexts = get_active_contexts(conn, user_id, current_date)
                dampened_indicators, applied_contexts = apply_context_dampening(indicators, contexts)

                # 5. Risk score calculation
                result = compute_risk_score(
                    user_id=user_id,
                    pseudonym_id=pseudonym_id,
                    alert_date=current_date,
                    indicators=dampened_indicators,
                    context_applied=applied_contexts,
                    baseline_confidence=confidence,
                    conn=conn,
                )

                if result["risk_score"] >= MIN_SCORE_TO_SAVE:
                    alerts_created += 1

                    # Link alert to ground truth scenario if matching
                    scenario = conn.execute(
                        """SELECT scenario_id FROM ground_truth
                           WHERE user_id = ? AND start_time <= ? AND end_time >= ?""",
                        (user_id, date_str, date_str)
                    ).fetchone()
                    if scenario:
                        conn.execute(
                            "UPDATE alerts SET scenario_id = ? WHERE alert_id = ?",
                            (scenario[0], result["alert_id"])
                        )
                        conn.commit()

            except Exception as e:
                logger.warning(f"Error evaluating {user_id} on {current_date}: {e}")

        current_date += timedelta(days=1)

    conn.commit()
    logger.info(f"Pipeline complete. Alerts created: {alerts_created}")

    # Evaluate against ground truth
    eval_results = evaluate_against_ground_truth(conn)
    logger.info(
        f"Evaluation metrics: Precision={eval_results.get('precision')}, "
        f"Recall={eval_results.get('recall')}, F1={eval_results.get('f1')}, "
        f"FPR={eval_results.get('false_positive_rate')}"
    )

    # Log to tamper-evident audit ledger
    log_audit_event(conn, actor="system", action="PIPELINE_RUN", details={
        "alerts_created": alerts_created,
        "evaluation": {k: v for k, v in eval_results.items() if k != "per_scenario"},
    })

    if close_conn:
        conn.close()

    return {"alerts_created": alerts_created, "evaluation": eval_results}


if __name__ == "__main__":
    result = run_pipeline()
    print(f"\nPipeline finished successfully! Alerts created: {result['alerts_created']}")
    eval_r = result["evaluation"]
    print(f"Metrics: Precision={eval_r.get('precision')}, Recall={eval_r.get('recall')}, F1={eval_r.get('f1')}")
