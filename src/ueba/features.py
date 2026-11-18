"""Feature engineering for daily/session behavior vectors."""
from __future__ import annotations
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any
import numpy as np


def compute_daily_features(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
) -> dict[str, float]:
    """
    Compute feature vector for a user on a given date.
    Used for IsolationForest and indicator comparison.
    """
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    features: dict[str, float] = {}

    # Login features
    logins = conn.execute(
        """SELECT timestamp, country, city, device_id, auth_result, auth_method
           FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end)
    ).fetchall()

    features["login_count"] = float(len(logins))
    features["failed_login_count"] = float(sum(1 for r in logins if r[4] == "failure"))
    features["unique_countries"] = float(len({r[1] for r in logins if r[1]}))
    features["unique_devices"] = float(len({r[3] for r in logins if r[3]}))

    # Hour distribution for logins
    login_hours = []
    for r in logins:
        try:
            dt = datetime.fromisoformat(r[0])
            login_hours.append(dt.hour)
        except (ValueError, TypeError):
            pass

    features["mean_login_hour"] = float(np.mean(login_hours)) if login_hours else 12.0
    features["min_login_hour"] = float(min(login_hours)) if login_hours else 0.0

    # Download features
    downloads = conn.execute(
        """SELECT bytes, file_count, destination_type
           FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end)
    ).fetchall()

    features["total_bytes_downloaded"] = float(sum(r[0] for r in downloads))
    features["total_files_downloaded"] = float(sum(r[1] for r in downloads))
    features["download_count"] = float(len(downloads))
    features["external_downloads"] = float(sum(1 for r in downloads if r[2] in ("personal_device", "external_share")))

    # File access features
    file_accesses = conn.execute(
        """SELECT resource_id, action
           FROM file_access_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end)
    ).fetchall()

    features["file_access_count"] = float(len(file_accesses))
    features["unique_resources_accessed"] = float(len({r[0] for r in file_accesses}))
    features["delete_actions"] = float(sum(1 for r in file_accesses if r[1] == "delete"))
    features["share_actions"] = float(sum(1 for r in file_accesses if r[1] == "share"))

    # Privilege features
    privs = conn.execute(
        """SELECT action FROM privilege_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end)
    ).fetchall()

    features["privilege_action_count"] = float(len(privs))
    features["escalation_actions"] = float(sum(1 for r in privs if r[0] in ("role_grant", "group_change")))

    # Sensitive resource access
    sensitive_access = conn.execute(
        """SELECT COUNT(*) FROM file_access_events fa
           JOIN resources r ON fa.resource_id = r.resource_id
           WHERE fa.user_id = ? AND fa.timestamp >= ? AND fa.timestamp < ?
           AND r.sensitivity IN ('Restricted', 'Confidential') AND fa.is_duplicate = 0""",
        (user_id, start, end)
    ).fetchone()[0]
    features["sensitive_resource_access"] = float(sensitive_access)

    return features
