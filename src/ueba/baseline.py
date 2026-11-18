"""Per-user and per-role baseline computation."""
from __future__ import annotations
import json
import math
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from typing import Any
import numpy as np
from .config import get_config


def compute_user_baseline(
    conn: sqlite3.Connection,
    user_id: str,
    as_of_date: date,
    window_days: int | None = None,
) -> dict[str, Any]:
    """
    Compute baseline metrics for a user as of a given date.
    Only uses data strictly before as_of_date (no leakage).
    Returns a dict of metric_name -> value.
    """
    cfg = get_config()
    if window_days is None:
        window_days = cfg.baseline.rolling_window_days

    window_start = (datetime.combine(as_of_date, datetime.min.time()) - timedelta(days=window_days)).isoformat()
    window_end = datetime.combine(as_of_date, datetime.min.time()).isoformat()

    baseline = {}

    # Login patterns
    logins = conn.execute(
        """SELECT timestamp, source_ip_truncated, country, city, device_id, auth_result
           FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, window_start, window_end)
    ).fetchall()

    # Hour-of-day histogram (smoothed with Laplace smoothing)
    hour_counts = [0] * 24
    for row in logins:
        try:
            dt = datetime.fromisoformat(row[0])
            hour_counts[dt.hour] += 1
        except (ValueError, TypeError):
            pass

    alpha = cfg.baseline.smoothing_alpha
    total = sum(hour_counts) + 24 * alpha
    hour_hist = [(c + alpha) / total for c in hour_counts]
    baseline["hour_histogram"] = hour_hist

    # Typical working window: hours with probability > threshold
    if sum(hour_counts) > 0:
        mean_count = sum(hour_counts) / 24
        active_hours = [h for h, c in enumerate(hour_counts) if c > mean_count * 0.3]
        baseline["typical_start_hour"] = min(active_hours) if active_hours else 9
        baseline["typical_end_hour"] = max(active_hours) if active_hours else 17
    else:
        # Use user's configured schedule
        user_row = conn.execute(
            "SELECT work_start_hour, work_end_hour FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if user_row:
            baseline["typical_start_hour"] = user_row[0]
            baseline["typical_end_hour"] = user_row[1]
        else:
            baseline["typical_start_hour"] = 9
            baseline["typical_end_hour"] = 17

    # Countries, cities, devices seen
    baseline["known_countries"] = list({r[2] for r in logins if r[2]})
    baseline["known_cities"] = list({r[3] for r in logins if r[3]})
    baseline["known_devices"] = list({r[4] for r in logins if r[4]})

    # Failed login rate
    total_logins = len(logins)
    failed = sum(1 for r in logins if r[5] == "failure")
    baseline["failed_login_rate"] = failed / max(total_logins, 1)

    # Download volume: median and MAD (robust stats)
    downloads = conn.execute(
        """SELECT date(timestamp), SUM(bytes), SUM(file_count)
           FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0
           GROUP BY date(timestamp)""",
        (user_id, window_start, window_end)
    ).fetchall()

    if downloads:
        daily_bytes = [r[1] for r in downloads]
        daily_files = [r[2] for r in downloads]
        baseline["download_median_bytes"] = float(np.median(daily_bytes))
        baseline["download_mad_bytes"] = float(np.median(np.abs(np.array(daily_bytes) - np.median(daily_bytes))))
        baseline["download_median_files"] = float(np.median(daily_files))
        baseline["download_mad_files"] = float(np.median(np.abs(np.array(daily_files) - np.median(daily_files))))
    else:
        baseline["download_median_bytes"] = 0.0
        baseline["download_mad_bytes"] = 1.0
        baseline["download_median_files"] = 0.0
        baseline["download_mad_files"] = 1.0

    # Resource access set
    file_rows = conn.execute(
        """SELECT resource_id FROM file_access_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, window_start, window_end)
    ).fetchall()
    baseline["known_resources"] = list({r[0] for r in file_rows})

    # Daily file access count
    daily_fa = conn.execute(
        """SELECT date(timestamp), COUNT(*) FROM file_access_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0
           GROUP BY date(timestamp)""",
        (user_id, window_start, window_end)
    ).fetchall()
    if daily_fa:
        fa_counts = [r[1] for r in daily_fa]
        baseline["file_access_median"] = float(np.median(fa_counts))
        baseline["file_access_mad"] = float(np.median(np.abs(np.array(fa_counts) - np.median(fa_counts))))
    else:
        baseline["file_access_median"] = 0.0
        baseline["file_access_mad"] = 1.0

    # Privilege action frequency
    priv_count = conn.execute(
        """SELECT COUNT(*) FROM privilege_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, window_start, window_end)
    ).fetchone()[0]
    baseline["privilege_actions_per_day"] = priv_count / max(window_days, 1)

    # Download destinations seen
    dest_rows = conn.execute(
        """SELECT DISTINCT destination_type FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, window_start, window_end)
    ).fetchall()
    baseline["known_destinations"] = [r[0] for r in dest_rows]

    # Baseline confidence
    days_of_history = conn.execute(
        """SELECT COUNT(DISTINCT date(timestamp)) FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ?""",
        (user_id, window_start, window_end)
    ).fetchone()[0]

    min_days = cfg.baseline.min_days_for_full_confidence
    min_events = cfg.baseline.min_events_for_full_confidence
    days_confidence = min(1.0, days_of_history / min_days)
    events_confidence = min(1.0, total_logins / min_events)
    baseline["confidence"] = round((days_confidence + events_confidence) / 2, 3)
    baseline["days_of_history"] = days_of_history

    return baseline


def compute_role_baseline(
    conn: sqlite3.Connection,
    role: str,
    as_of_date: date,
    window_days: int | None = None,
) -> dict[str, Any]:
    """Compute aggregated baseline for a role (peer group)."""
    cfg = get_config()
    if window_days is None:
        window_days = cfg.baseline.rolling_window_days

    # Get all users with this role
    users = conn.execute("SELECT user_id FROM users WHERE role = ?", (role,)).fetchall()
    user_ids = [r[0] for r in users]

    if not user_ids:
        return {}

    all_baselines = []
    for uid in user_ids:
        bl = compute_user_baseline(conn, uid, as_of_date, window_days)
        all_baselines.append(bl)

    # Aggregate: median of medians for numeric fields
    def safe_median(vals):
        v = [x for x in vals if x is not None]
        return float(np.median(v)) if v else 0.0

    return {
        "download_median_bytes": safe_median([b.get("download_median_bytes", 0) for b in all_baselines]),
        "download_mad_bytes": safe_median([b.get("download_mad_bytes", 1) for b in all_baselines]),
        "download_median_files": safe_median([b.get("download_median_files", 0) for b in all_baselines]),
        "download_mad_files": safe_median([b.get("download_mad_files", 1) for b in all_baselines]),
        "file_access_median": safe_median([b.get("file_access_median", 0) for b in all_baselines]),
        "privilege_actions_per_day": safe_median([b.get("privilege_actions_per_day", 0) for b in all_baselines]),
        "typical_start_hour": int(safe_median([b.get("typical_start_hour", 9) for b in all_baselines])),
        "typical_end_hour": int(safe_median([b.get("typical_end_hour", 17) for b in all_baselines])),
        "failed_login_rate": safe_median([b.get("failed_login_rate", 0) for b in all_baselines]),
    }


def blend_baselines(user_baseline: dict, role_baseline: dict, confidence: float) -> dict:
    """
    Blend user and role baselines: effective = w*user + (1-w)*role
    where w = baseline confidence. Cold-start solution.
    """
    if not role_baseline:
        return user_baseline

    numeric_keys = [
        "download_median_bytes", "download_mad_bytes", "download_median_files",
        "download_mad_files", "file_access_median", "privilege_actions_per_day",
        "typical_start_hour", "typical_end_hour", "failed_login_rate",
    ]

    blended = dict(user_baseline)
    w = confidence

    for key in numeric_keys:
        u_val = user_baseline.get(key, 0)
        r_val = role_baseline.get(key, 0)
        blended[key] = w * u_val + (1 - w) * r_val

    return blended


def save_baseline_to_db(
    conn: sqlite3.Connection,
    user_id: str,
    computed_date: date,
    baseline: dict,
    baseline_type: str = "user",
) -> None:
    """Persist baseline to user_baselines table."""
    for metric_name, metric_value in baseline.items():
        bid = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO user_baselines (baseline_id, user_id, computed_date, baseline_type, metric_name, metric_value, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (bid, user_id, computed_date.isoformat(), baseline_type, metric_name,
             json.dumps(metric_value), baseline.get("confidence", 0.5))
        )
    conn.commit()


def get_saved_baseline(
    conn: sqlite3.Connection,
    user_id: str,
    computed_date: date,
) -> dict:
    """Retrieve a previously saved baseline from DB."""
    rows = conn.execute(
        """SELECT metric_name, metric_value, confidence FROM user_baselines
           WHERE user_id = ? AND computed_date = ? AND baseline_type = 'user'""",
        (user_id, computed_date.isoformat())
    ).fetchall()
    if not rows:
        return {}
    result = {}
    for row in rows:
        try:
            result[row[0]] = json.loads(row[1])
        except json.JSONDecodeError:
            result[row[0]] = row[1]
    return result
