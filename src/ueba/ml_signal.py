"""IsolationForest supporting ML signal for anomaly detection."""
from __future__ import annotations
import json
import sqlite3
from datetime import date, timedelta, datetime
from typing import Any
import numpy as np
from sklearn.ensemble import IsolationForest
from .config import get_config, load_scoring_weights
from .features import compute_daily_features

FEATURE_NAMES = [
    "login_count", "failed_login_count", "unique_countries", "unique_devices",
    "mean_login_hour", "min_login_hour", "total_bytes_downloaded", "total_files_downloaded",
    "download_count", "external_downloads", "file_access_count", "unique_resources_accessed",
    "delete_actions", "share_actions", "privilege_action_count", "escalation_actions",
    "sensitive_resource_access",
]


_TRAINED_MODEL_CACHE: dict[str, tuple[IsolationForest, np.ndarray, np.ndarray] | None] = {}


def _get_training_features(
    conn: sqlite3.Connection,
    user_id: str,
    baseline_end_date: date,
    window_days: int = 60,
) -> np.ndarray:
    """Extract feature matrix from baseline period for training."""
    rows = []
    start = baseline_end_date - timedelta(days=window_days)
    current = start
    while current < baseline_end_date:
        feats = compute_daily_features(conn, user_id, current)
        rows.append([feats.get(f, 0.0) for f in FEATURE_NAMES])
        current += timedelta(days=1)
    return np.array(rows, dtype=float)


def compute_ml_anomaly_score(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline_end_date: date,
    weights: dict | None = None,
) -> dict[str, Any] | None:
    """
    Train IsolationForest on baseline period, score target_date.
    Returns indicator dict or None if insufficient data / not anomalous.
    """
    cfg = get_config()
    if weights is None:
        weights = load_scoring_weights()

    # Get cached model or train once per user
    if user_id in _TRAINED_MODEL_CACHE:
        cached = _TRAINED_MODEL_CACHE[user_id]
        if cached is None:
            return None
        clf, baseline_means, baseline_stds = cached
    else:
        # Get training data
        X_train = _get_training_features(conn, user_id, baseline_end_date)
        non_zero = np.any(X_train != 0, axis=1).sum()
        if non_zero < 10:
            _TRAINED_MODEL_CACHE[user_id] = None
            return None

        clf = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=cfg.seed,
        )
        clf.fit(X_train)
        baseline_means = X_train.mean(axis=0)
        baseline_stds = X_train.std(axis=0) + 1e-6
        _TRAINED_MODEL_CACHE[user_id] = (clf, baseline_means, baseline_stds)

    # Score target date
    target_feats = compute_daily_features(conn, user_id, target_date)
    X_test = np.array([[target_feats.get(f, 0.0) for f in FEATURE_NAMES]])

    # IsolationForest score_samples: more negative = more anomalous
    raw_score = clf.score_samples(X_test)[0]
    # Normalize to [0, 1]
    normalized = max(0.0, min(1.0, (-raw_score - 0.1) / 0.4))

    if normalized < 0.35:
        return None  # Not anomalous enough to report

    # Find top contributing features
    test_values = X_test[0]
    deviations = np.abs(test_values - baseline_means) / baseline_stds
    top_idx = np.argsort(deviations)[::-1][:3]
    top_features = [
        (FEATURE_NAMES[i], float(deviations[i]), float(test_values[i]), float(baseline_means[i]))
        for i in top_idx
    ]

    weight_cfg = weights.get("ML_ANOMALY_SUPPORT")
    base_points = weight_cfg.base_points if weight_cfg else 15
    severity_points = int(base_points * normalized)

    top_feat_desc = "; ".join(
        f"{f} (observed={v:.1f}, baseline avg={b:.1f})"
        for f, _, v, b in top_features
    )

    return {
        "indicator_id": f"ML_ANOMALY_SUPPORT_{user_id}_{target_date}",
        "name": "ML_ANOMALY_SUPPORT",
        "severity_points": severity_points,
        "confidence": round(normalized, 2),
        "description": f"IsolationForest flags unusual daily activity pattern (supporting signal only). Top deviating features: {top_feat_desc}",
        "evidence_event_ids": [],
        "observed_value": round(normalized, 3),
        "baseline_value": 0.0,
        "why_it_matters": "Machine learning model trained on 60-day baseline detects unusual patterns in aggregate behavior. This is a supporting indicator only and should not be used as sole evidence.",
    }
