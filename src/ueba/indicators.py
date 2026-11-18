"""Rule-based behavioral indicators for UEBA detection."""
from __future__ import annotations
import math
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

from .config import get_config, load_scoring_weights

# ---------------------------------------------------------------------------
# City coordinates for impossible travel (lat, lon)
# ---------------------------------------------------------------------------
CITY_COORDS: dict[str, tuple[float, float]] = {
    # North America
    "New York": (40.7128, -74.0060),
    "Los Angeles": (34.0522, -118.2437),
    "Chicago": (41.8781, -87.6298),
    "Houston": (29.7604, -95.3698),
    "San Francisco": (37.7749, -122.4194),
    "Seattle": (47.6062, -122.3321),
    "Boston": (42.3601, -71.0589),
    "Miami": (25.7617, -80.1918),
    "Denver": (39.7392, -104.9903),
    "Atlanta": (33.7490, -84.3880),
    "Toronto": (43.6532, -79.3832),
    "Vancouver": (49.2827, -123.1207),
    "Montreal": (45.5017, -73.5673),
    # Europe
    "London": (51.5074, -0.1278),
    "Paris": (48.8566, 2.3522),
    "Berlin": (52.5200, 13.4050),
    "Amsterdam": (52.3676, 4.9041),
    "Madrid": (40.4168, -3.7038),
    "Rome": (41.9028, 12.4964),
    "Zurich": (47.3769, 8.5417),
    "Dublin": (53.3498, -6.2603),
    "Stockholm": (59.3293, 18.0686),
    "Warsaw": (52.2297, 21.0122),
    "Prague": (50.0755, 14.4378),
    "Vienna": (48.2082, 16.3738),
    "Brussels": (50.8503, 4.3517),
    "Copenhagen": (55.6761, 12.5683),
    "Helsinki": (60.1699, 24.9384),
    "Oslo": (59.9139, 10.7522),
    "Lisbon": (38.7223, -9.1393),
    # Asia
    "Tokyo": (35.6762, 139.6503),
    "Beijing": (39.9042, 116.4074),
    "Shanghai": (31.2304, 121.4737),
    "Singapore": (1.3521, 103.8198),
    "Hong Kong": (22.3193, 114.1694),
    "Seoul": (37.5665, 126.9780),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.7041, 77.1025),
    "Bangalore": (12.9716, 77.5946),
    "Jakarta": (-6.2088, 106.8456),
    "Bangkok": (13.7563, 100.5018),
    "Kuala Lumpur": (3.1390, 101.6869),
    "Dubai": (25.2048, 55.2708),
    "Riyadh": (24.7136, 46.6753),
    "Tel Aviv": (32.0853, 34.7818),
    "Istanbul": (41.0082, 28.9784),
    # Other
    "Sydney": (-33.8688, 151.2093),
    "Melbourne": (-37.8136, 144.9631),
    "Auckland": (-36.8509, 174.7645),
    "Cairo": (30.0444, 31.2357),
    "Lagos": (6.5244, 3.3792),
    "Nairobi": (-1.2921, 36.8219),
    "Johannesburg": (-26.2041, 28.0473),
    "São Paulo": (-23.5505, -46.6333),
    "Buenos Aires": (-34.6037, -58.3816),
    "Mexico City": (19.4326, -99.1332),
    "Bogotá": (4.7110, -74.0721),
    "Lima": (-12.0464, -77.0428),
}

RISKY_DESTINATIONS = {"personal_device", "external_share", "usb_drive", "personal_email", "cloud_personal"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _weight(weights: dict, name: str, default: int = 20) -> int:
    cfg = weights.get(name)
    return cfg.base_points if cfg else default


# ---------------------------------------------------------------------------
# 1. UNUSUAL_HOUR
# ---------------------------------------------------------------------------
def check_unusual_hour(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    """Flag logins/activity outside the user's learned working-hour window."""
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    logins = conn.execute(
        """SELECT event_id, timestamp FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end),
    ).fetchall()

    if not logins:
        return []

    typical_start = baseline.get("typical_start_hour", 9)
    typical_end = baseline.get("typical_end_hour", 17)
    hour_hist = baseline.get("hour_histogram")

    out_of_hours_events = []
    for event_id, ts in logins:
        try:
            hour = datetime.fromisoformat(ts).hour
        except (ValueError, TypeError):
            continue
        is_outside = hour < typical_start or hour > typical_end
        if hour_hist and len(hour_hist) == 24:
            prob = hour_hist[hour]
            if is_outside and prob < 0.05:
                out_of_hours_events.append((event_id, ts, hour))
        else:
            if is_outside:
                out_of_hours_events.append((event_id, ts, hour))

    if not out_of_hours_events:
        return []

    base_pts = _weight(weights, "UNUSUAL_HOUR", 20)
    # Scale by number of off-hours events (diminishing)
    severity = min(base_pts, int(base_pts * (1 - 0.5 ** len(out_of_hours_events))))
    if severity < 5:
        severity = base_pts // 2

    earliest_hour = min(h for _, _, h in out_of_hours_events)
    return [{
        "indicator_id": f"UNUSUAL_HOUR_{user_id}_{target_date}",
        "name": "UNUSUAL_HOUR",
        "severity_points": severity,
        "confidence": round(min(1.0, len(out_of_hours_events) / 3), 2),
        "description": (
            f"User logged in at hour {earliest_hour:02d}:00, "
            f"outside their learned working window ({int(typical_start):02d}:00–{int(typical_end):02d}:00). "
            f"{len(out_of_hours_events)} off-hours login(s) detected."
        ),
        "evidence_event_ids": [e[0] for e in out_of_hours_events],
        "observed_value": float(earliest_hour),
        "baseline_value": float(typical_start),
        "why_it_matters": (
            "Logins at unusual times may indicate account compromise, unauthorized sharing of credentials, "
            "or insider threat activity. Time-of-day is a key behavioral baseline."
        ),
    }]


# ---------------------------------------------------------------------------
# 2. NEW_COUNTRY / NEW_CITY
# ---------------------------------------------------------------------------
def check_new_country(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    logins = conn.execute(
        """SELECT event_id, timestamp, country FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0 AND country IS NOT NULL""",
        (user_id, start, end),
    ).fetchall()

    known_countries = set(baseline.get("known_countries", []))
    try:
        u_row = conn.execute("SELECT home_country FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if u_row and u_row[0]:
            known_countries.add(u_row[0])
    except Exception:
        pass
    indicators = []

    new_country_events = [(eid, ts, c) for eid, ts, c in logins if c not in known_countries]
    if not new_country_events:
        return []

    new_countries = list({c for _, _, c in new_country_events})
    base_pts = _weight(weights, "NEW_COUNTRY", 35)

    indicators.append({
        "indicator_id": f"NEW_COUNTRY_{user_id}_{target_date}",
        "name": "NEW_COUNTRY",
        "severity_points": base_pts,
        "confidence": 0.9,
        "description": (
            f"Login detected from new country/countries: {', '.join(new_countries)}. "
            f"Known countries in baseline: {', '.join(known_countries) or 'none'}."
        ),
        "evidence_event_ids": [e[0] for e in new_country_events],
        "observed_value": new_countries[0] if new_countries else "unknown",
        "baseline_value": list(known_countries),
        "why_it_matters": (
            "A login from a country never previously observed for this user is a high-fidelity signal "
            "of either travel (check context) or account compromise."
        ),
    })
    return indicators


def check_new_city(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    logins = conn.execute(
        """SELECT event_id, timestamp, city FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0 AND city IS NOT NULL""",
        (user_id, start, end),
    ).fetchall()

    known_cities = set(baseline.get("known_cities", []))
    try:
        u_row = conn.execute("SELECT home_city FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if u_row and u_row[0]:
            known_cities.add(u_row[0])
    except Exception:
        pass
    new_city_events = [(eid, ts, c) for eid, ts, c in logins if c not in known_cities]
    if not new_city_events:
        return []

    new_cities = list({c for _, _, c in new_city_events})
    base_pts = _weight(weights, "NEW_CITY", 15)

    return [{
        "indicator_id": f"NEW_CITY_{user_id}_{target_date}",
        "name": "NEW_CITY",
        "severity_points": base_pts,
        "confidence": 0.75,
        "description": (
            f"Login detected from new city/cities: {', '.join(new_cities)}. "
            f"Known cities: {', '.join(known_cities) or 'none'}."
        ),
        "evidence_event_ids": [e[0] for e in new_city_events],
        "observed_value": new_cities[0] if new_cities else "unknown",
        "baseline_value": list(known_cities),
        "why_it_matters": (
            "A new city is a weaker signal than a new country but still warrants attention, especially "
            "when combined with other anomalies."
        ),
    }]


# ---------------------------------------------------------------------------
# 3. IMPOSSIBLE_TRAVEL
# ---------------------------------------------------------------------------
def check_impossible_travel(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    """Detect two successful logins from different cities that imply physically impossible speed."""
    cfg = get_config()
    threshold_kmh = cfg.thresholds.impossible_travel_kmh

    # Extend window slightly to catch overnight travel
    window_start = (datetime.combine(target_date, datetime.min.time()) - timedelta(hours=4)).isoformat()
    window_end = (datetime.combine(target_date + timedelta(days=1), datetime.min.time()) + timedelta(hours=4)).isoformat()

    logins = conn.execute(
        """SELECT event_id, timestamp, city, country, auth_result FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
           AND is_duplicate = 0 AND auth_result = 'success'
           ORDER BY timestamp""",
        (user_id, window_start, window_end),
    ).fetchall()

    if len(logins) < 2:
        return []

    base_pts = _weight(weights, "IMPOSSIBLE_TRAVEL", 60)
    indicators = []

    for i in range(len(logins) - 1):
        for j in range(i + 1, len(logins)):
            eid1, ts1, city1, country1, _ = logins[i]
            eid2, ts2, city2, country2, _ = logins[j]

            if not city1 or not city2 or city1 == city2:
                continue
            if city1 not in CITY_COORDS or city2 not in CITY_COORDS:
                # Try country-level fallback
                continue

            try:
                dt1 = datetime.fromisoformat(ts1)
                dt2 = datetime.fromisoformat(ts2)
                elapsed_hours = abs((dt2 - dt1).total_seconds()) / 3600.0
            except (ValueError, TypeError):
                continue

            if elapsed_hours < 0.01:
                continue

            dist_km = _haversine_km(*CITY_COORDS[city1], *CITY_COORDS[city2])
            # Respect same-country corporate VPN gateway switching
            if country1 == country2 and dist_km < 2500:
                continue
            speed_kmh = dist_km / elapsed_hours

            if speed_kmh > threshold_kmh:
                # Only flag once (the most extreme pair)
                indicators.append({
                    "indicator_id": f"IMPOSSIBLE_TRAVEL_{user_id}_{target_date}",
                    "name": "IMPOSSIBLE_TRAVEL",
                    "severity_points": base_pts,
                    "confidence": min(1.0, round(speed_kmh / (threshold_kmh * 2), 2)),
                    "description": (
                        f"Login from {city1} at {ts1} and from {city2} at {ts2} "
                        f"imply travel at {speed_kmh:.0f} km/h over {dist_km:.0f} km "
                        f"in {elapsed_hours:.1f} hours. "
                        f"Threshold: {threshold_kmh} km/h."
                    ),
                    "evidence_event_ids": [eid1, eid2],
                    "observed_value": round(speed_kmh, 1),
                    "baseline_value": float(threshold_kmh),
                    "why_it_matters": (
                        "Physically impossible travel speed between two successful logins strongly suggests "
                        "credential sharing, account compromise, or VPN/proxy usage to falsify location. "
                        "This indicator cannot be context-dampened."
                    ),
                })
                return indicators  # One is enough per day

    return indicators


# ---------------------------------------------------------------------------
# 4. NEW_DEVICE
# ---------------------------------------------------------------------------
def check_new_device(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    logins = conn.execute(
        """SELECT event_id, timestamp, device_id FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
           AND is_duplicate = 0 AND device_id IS NOT NULL""",
        (user_id, start, end),
    ).fetchall()

    known_devices = set(baseline.get("known_devices", []))
    try:
        assigned = conn.execute("SELECT device_id FROM devices WHERE user_id = ?", (user_id,)).fetchall()
        known_devices.update(row[0] for row in assigned)
    except Exception:
        pass
    new_device_events = [(eid, ts, d) for eid, ts, d in logins if d not in known_devices]
    if not new_device_events:
        return []

    new_devices = list({d for _, _, d in new_device_events})
    base_pts = _weight(weights, "NEW_DEVICE", 25)

    return [{
        "indicator_id": f"NEW_DEVICE_{user_id}_{target_date}",
        "name": "NEW_DEVICE",
        "severity_points": base_pts,
        "confidence": 0.85,
        "description": (
            f"Login from {len(new_devices)} previously unseen device(s): {', '.join(new_devices[:3])}. "
            f"User has {len(known_devices)} known device(s) in baseline."
        ),
        "evidence_event_ids": [e[0] for e in new_device_events],
        "observed_value": float(len(new_devices)),
        "baseline_value": float(len(known_devices)),
        "why_it_matters": (
            "An unrecognized device may indicate credential theft or policy violation. "
            "Combined with new location, this is a strong compound signal."
        ),
    }]


# ---------------------------------------------------------------------------
# 5. FAILED_LOGIN_BURST_THEN_SUCCESS
# ---------------------------------------------------------------------------
def check_failed_login_burst_then_success(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    cfg = get_config()
    burst_count = cfg.thresholds.failed_login_burst_count
    burst_minutes = cfg.thresholds.failed_login_burst_minutes

    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    events = conn.execute(
        """SELECT event_id, timestamp, auth_result FROM login_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0
           ORDER BY timestamp""",
        (user_id, start, end),
    ).fetchall()

    if not events:
        return []

    # Sliding window: find burst of failures followed by success
    base_pts = _weight(weights, "FAILED_LOGIN_BURST_THEN_SUCCESS", 45)

    for i, (eid, ts, result) in enumerate(events):
        if result != "success":
            continue
        # Look back for burst of failures within window
        try:
            success_time = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            continue

        window_start_dt = success_time - timedelta(minutes=burst_minutes)
        failures_in_window = []
        for j in range(i):
            prev_eid, prev_ts, prev_result = events[j]
            if prev_result != "failure":
                continue
            try:
                prev_dt = datetime.fromisoformat(prev_ts)
            except (ValueError, TypeError):
                continue
            if prev_dt >= window_start_dt:
                failures_in_window.append((prev_eid, prev_ts))

        if len(failures_in_window) >= burst_count:
            all_eids = [f[0] for f in failures_in_window] + [eid]
            # Confidence scales with number of failures
            confidence = min(1.0, len(failures_in_window) / (burst_count * 2))
            return [{
                "indicator_id": f"FAILED_LOGIN_BURST_THEN_SUCCESS_{user_id}_{target_date}",
                "name": "FAILED_LOGIN_BURST_THEN_SUCCESS",
                "severity_points": base_pts,
                "confidence": round(confidence, 2),
                "description": (
                    f"{len(failures_in_window)} failed login attempt(s) within {burst_minutes} minutes "
                    f"followed by a successful login at {ts}. "
                    f"This pattern resembles a credential brute-force or spray attack."
                ),
                "evidence_event_ids": all_eids,
                "observed_value": float(len(failures_in_window)),
                "baseline_value": float(burst_count - 1),
                "why_it_matters": (
                    "Repeated failures before success is a classic credential attack pattern. "
                    "Could indicate brute force, credential stuffing, or password spray. "
                    "This indicator cannot be context-dampened."
                ),
            }]

    return []


# ---------------------------------------------------------------------------
# 6. DOWNLOAD_VOLUME_SPIKE
# ---------------------------------------------------------------------------
def check_download_volume_spike(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    cfg = get_config()
    mad_z_threshold = cfg.thresholds.download_spike_mad_z

    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    rows = conn.execute(
        """SELECT event_id, bytes, file_count FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end),
    ).fetchall()

    if not rows:
        return []

    total_bytes = sum(r[1] for r in rows)
    total_files = sum(r[2] for r in rows)

    median_bytes = baseline.get("download_median_bytes", 0.0)
    mad_bytes = max(baseline.get("download_mad_bytes", 1.0), 1.0)

    # Robust z-score (modified Z-score using MAD)
    # Constant 0.6745 so MAD ≈ std for normal distribution
    robust_z = (total_bytes - median_bytes) / (mad_bytes / 0.6745)

    if robust_z < mad_z_threshold:
        return []

    base_pts = _weight(weights, "DOWNLOAD_VOLUME_SPIKE", 40)
    # Scale severity with z-score
    severity = min(base_pts, int(base_pts * (robust_z / (mad_z_threshold * 2))))
    if severity < base_pts // 2:
        severity = base_pts // 2

    return [{
        "indicator_id": f"DOWNLOAD_VOLUME_SPIKE_{user_id}_{target_date}",
        "name": "DOWNLOAD_VOLUME_SPIKE",
        "severity_points": severity,
        "confidence": round(min(1.0, robust_z / (mad_z_threshold * 3)), 2),
        "description": (
            f"User downloaded {total_bytes / 1e6:.1f} MB ({total_files} files) today. "
            f"Baseline median: {median_bytes / 1e6:.1f} MB. "
            f"Robust z-score: {robust_z:.1f} (threshold: {mad_z_threshold})."
        ),
        "evidence_event_ids": [r[0] for r in rows],
        "observed_value": float(total_bytes),
        "baseline_value": float(median_bytes),
        "why_it_matters": (
            "A sudden spike in download volume, especially near resignation or project end, "
            "is a classic data exfiltration signal. Robust z-score tolerates skewed baselines."
        ),
    }]


# ---------------------------------------------------------------------------
# 7. DOWNLOAD_TREND (Mann-Kendall style monotone slope test)
# ---------------------------------------------------------------------------
def check_download_trend(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    """Detect a sustained upward trend in daily download volume over recent N days."""
    cfg = get_config()
    trend_days = cfg.thresholds.download_trend_days

    # Look back over trend_days including today
    window_start = (datetime.combine(target_date, datetime.min.time()) - timedelta(days=trend_days - 1)).isoformat()
    window_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    rows = conn.execute(
        """SELECT date(timestamp) as day, SUM(bytes) as total_bytes
           FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0
           GROUP BY day ORDER BY day""",
        (user_id, window_start, window_end),
    ).fetchall()

    if len(rows) < trend_days:
        return []

    daily_bytes = [r[1] for r in rows[-trend_days:]]

    # Mann-Kendall: count concordant vs discordant pairs
    n = len(daily_bytes)
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = daily_bytes[j] - daily_bytes[i]
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1

    # Maximum possible S = n*(n-1)/2
    max_s = n * (n - 1) / 2
    tau = s / max_s if max_s > 0 else 0.0

    # Only flag strong upward trends
    if tau < 0.6:
        return []

    base_pts = _weight(weights, "DOWNLOAD_TREND", 30)
    severity = int(base_pts * tau)

    slope_mb_per_day = (daily_bytes[-1] - daily_bytes[0]) / max(1e6 * (trend_days - 1), 1)

    return [{
        "indicator_id": f"DOWNLOAD_TREND_{user_id}_{target_date}",
        "name": "DOWNLOAD_TREND",
        "severity_points": severity,
        "confidence": round(tau, 2),
        "description": (
            f"Sustained upward download trend over {trend_days} days. "
            f"Kendall tau: {tau:.2f}. "
            f"Slope: ~{slope_mb_per_day:.1f} MB/day increase. "
            f"Today: {daily_bytes[-1] / 1e6:.1f} MB, {trend_days} days ago: {daily_bytes[0] / 1e6:.1f} MB."
        ),
        "evidence_event_ids": [],
        "observed_value": round(tau, 3),
        "baseline_value": 0.6,
        "why_it_matters": (
            "A gradual, sustained increase in download volume can indicate slow data staging "
            "before exfiltration — harder to detect than a single spike."
        ),
    }]


# ---------------------------------------------------------------------------
# 8. NEW_RESOURCE_ACCESS
# ---------------------------------------------------------------------------
def check_new_resource_access(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    accesses = conn.execute(
        """SELECT fa.event_id, fa.resource_id, r.sensitivity, r.name
           FROM file_access_events fa
           LEFT JOIN resources r ON fa.resource_id = r.resource_id
           WHERE fa.user_id = ? AND fa.timestamp >= ? AND fa.timestamp < ? AND fa.is_duplicate = 0""",
        (user_id, start, end),
    ).fetchall()

    known_resources = set(baseline.get("known_resources", []))
    new_accesses = [(eid, rid, sens, name) for eid, rid, sens, name in accesses if rid not in known_resources]

    if not new_accesses:
        return []

    base_pts = _weight(weights, "NEW_RESOURCE_ACCESS", 20)

    # Weight higher for sensitive resources
    sensitive_new = [a for a in new_accesses if a[2] in ("Restricted", "Confidential")]
    if sensitive_new:
        severity = int(base_pts * 1.5)
        confidence = 0.8
        desc_suffix = f" ({len(sensitive_new)} are Restricted/Confidential)."
    else:
        severity = base_pts
        confidence = 0.65
        desc_suffix = "."

    new_resource_names = [a[3] or a[1] for a in new_accesses[:5]]

    return [{
        "indicator_id": f"NEW_RESOURCE_ACCESS_{user_id}_{target_date}",
        "name": "NEW_RESOURCE_ACCESS",
        "severity_points": severity,
        "confidence": confidence,
        "description": (
            f"User accessed {len(new_accesses)} resource(s) not seen in their baseline: "
            f"{', '.join(new_resource_names)}{desc_suffix}"
        ),
        "evidence_event_ids": [a[0] for a in new_accesses],
        "observed_value": float(len(new_accesses)),
        "baseline_value": float(len(known_resources)),
        "why_it_matters": (
            "Accessing resources outside the user's known set, especially sensitive ones, "
            "may indicate privilege abuse, reconnaissance, or data staging."
        ),
    }]


# ---------------------------------------------------------------------------
# 9. OUT_OF_ROLE_SENSITIVE_ACCESS
# ---------------------------------------------------------------------------
def check_out_of_role_sensitive_access(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    # Get user's role
    user_row = conn.execute(
        "SELECT role FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not user_row:
        return []
    user_role = user_row[0]

    # Find accesses to sensitive resources where user's role is NOT allowed
    out_of_role = conn.execute(
        """SELECT fa.event_id, fa.resource_id, r.sensitivity, r.name
           FROM file_access_events fa
           JOIN resources r ON fa.resource_id = r.resource_id
           WHERE fa.user_id = ? AND fa.timestamp >= ? AND fa.timestamp < ?
           AND r.sensitivity IN ('Restricted', 'Confidential') AND fa.is_duplicate = 0
           AND NOT EXISTS (
               SELECT 1 FROM role_resource_access rra
               WHERE rra.role = ? AND rra.resource_id = fa.resource_id
           )""",
        (user_id, start, end, user_role),
    ).fetchall()

    if not out_of_role:
        return []

    base_pts = _weight(weights, "OUT_OF_ROLE_SENSITIVE_ACCESS", 45)
    restricted = [a for a in out_of_role if a[2] == "Restricted"]
    severity = base_pts + (10 if restricted else 0)

    return [{
        "indicator_id": f"OUT_OF_ROLE_SENSITIVE_ACCESS_{user_id}_{target_date}",
        "name": "OUT_OF_ROLE_SENSITIVE_ACCESS",
        "severity_points": min(severity, 100),
        "confidence": 0.85,
        "description": (
            f"User (role: {user_role}) accessed {len(out_of_role)} sensitive resource(s) "
            f"outside their role permissions. "
            f"Resources: {', '.join(a[3] or a[1] for a in out_of_role[:3])}."
        ),
        "evidence_event_ids": [a[0] for a in out_of_role],
        "observed_value": float(len(out_of_role)),
        "baseline_value": 0.0,
        "why_it_matters": (
            "Accessing sensitive data outside one's job role is a serious access control violation "
            "that may indicate privilege abuse or lateral movement after compromise."
        ),
    }]


# ---------------------------------------------------------------------------
# 10. OFF_HOURS_PRIVILEGE_USE
# ---------------------------------------------------------------------------
def check_off_hours_privilege_use(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    privs = conn.execute(
        """SELECT event_id, timestamp, action FROM privilege_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end),
    ).fetchall()

    if not privs:
        return []

    typical_start = baseline.get("typical_start_hour", 9)
    typical_end = baseline.get("typical_end_hour", 17)

    off_hours = []
    for eid, ts, action in privs:
        try:
            hour = datetime.fromisoformat(ts).hour
        except (ValueError, TypeError):
            continue
        if hour < typical_start or hour > typical_end:
            off_hours.append((eid, ts, action, hour))

    if not off_hours:
        return []

    base_pts = _weight(weights, "OFF_HOURS_PRIVILEGE_USE", 35)
    actions = list({a[2] for a in off_hours})

    return [{
        "indicator_id": f"OFF_HOURS_PRIVILEGE_USE_{user_id}_{target_date}",
        "name": "OFF_HOURS_PRIVILEGE_USE",
        "severity_points": base_pts,
        "confidence": min(1.0, round(len(off_hours) / 3, 2)),
        "description": (
            f"{len(off_hours)} privileged action(s) performed outside working hours "
            f"({typical_start:02d}:00–{typical_end:02d}:00). "
            f"Actions: {', '.join(actions)}."
        ),
        "evidence_event_ids": [a[0] for a in off_hours],
        "observed_value": float(min(a[3] for a in off_hours)),
        "baseline_value": float(typical_start),
        "why_it_matters": (
            "Privileged actions outside working hours are a significant risk signal — "
            "attackers who compromise admin accounts often operate during off-hours to avoid detection."
        ),
    }]


# ---------------------------------------------------------------------------
# 11. PRIVILEGE_ESCALATION_SEQUENCE
# ---------------------------------------------------------------------------
def check_privilege_escalation_sequence(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    privs = conn.execute(
        """SELECT event_id, timestamp, action FROM privilege_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0
           ORDER BY timestamp""",
        (user_id, start, end),
    ).fetchall()

    escalation_actions = {"role_grant", "group_change", "sudo_use", "admin_grant", "privilege_grant"}
    escalation_events = [(eid, ts, act) for eid, ts, act in privs if act in escalation_actions]

    if len(escalation_events) < 2:
        # Single escalation action is still worth flagging if it's admin-granting
        if escalation_events and escalation_events[0][2] in {"admin_grant", "privilege_grant", "role_grant"}:
            base_pts = _weight(weights, "PRIVILEGE_ESCALATION_SEQUENCE", 55)
            return [{
                "indicator_id": f"PRIVILEGE_ESCALATION_SEQUENCE_{user_id}_{target_date}",
                "name": "PRIVILEGE_ESCALATION_SEQUENCE",
                "severity_points": base_pts // 2,
                "confidence": 0.6,
                "description": (
                    f"Single high-risk privilege action detected: {escalation_events[0][2]} at {escalation_events[0][1]}."
                ),
                "evidence_event_ids": [escalation_events[0][0]],
                "observed_value": 1.0,
                "baseline_value": float(baseline.get("privilege_actions_per_day", 0)),
                "why_it_matters": (
                    "Privilege escalation is a key step in many attack kill chains, "
                    "enabling attackers to maintain persistence and expand access."
                ),
            }]
        return []

    base_pts = _weight(weights, "PRIVILEGE_ESCALATION_SEQUENCE", 55)
    actions = [a[2] for a in escalation_events]
    baseline_priv = baseline.get("privilege_actions_per_day", 0.0)

    return [{
        "indicator_id": f"PRIVILEGE_ESCALATION_SEQUENCE_{user_id}_{target_date}",
        "name": "PRIVILEGE_ESCALATION_SEQUENCE",
        "severity_points": base_pts,
        "confidence": min(1.0, round(len(escalation_events) / 3, 2)),
        "description": (
            f"Privilege escalation sequence detected: {len(escalation_events)} escalation action(s) today. "
            f"Actions: {', '.join(actions)}. "
            f"Baseline: {baseline_priv:.2f} privilege actions/day."
        ),
        "evidence_event_ids": [e[0] for e in escalation_events],
        "observed_value": float(len(escalation_events)),
        "baseline_value": baseline_priv,
        "why_it_matters": (
            "A sequence of privilege escalation actions in a short window is a strong indicator "
            "of active attack progression or insider threat executing a planned takeover."
        ),
    }]


# ---------------------------------------------------------------------------
# 12. RISKY_DESTINATION
# ---------------------------------------------------------------------------
def check_risky_destination(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    rows = conn.execute(
        """SELECT event_id, bytes, file_count, destination_type FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end),
    ).fetchall()

    risky_events = [(eid, b, fc, dest) for eid, b, fc, dest in rows if dest in RISKY_DESTINATIONS]
    if not risky_events:
        return []

    known_destinations = set(baseline.get("known_destinations", []))
    new_risky = [e for e in risky_events if e[3] not in known_destinations]

    base_pts = _weight(weights, "RISKY_DESTINATION", 35)
    total_bytes = sum(e[1] for e in risky_events)
    dest_types = list({e[3] for e in risky_events})

    # Higher severity if destination is new
    severity = base_pts if new_risky else base_pts // 2

    return [{
        "indicator_id": f"RISKY_DESTINATION_{user_id}_{target_date}",
        "name": "RISKY_DESTINATION",
        "severity_points": severity,
        "confidence": 0.75 if new_risky else 0.5,
        "description": (
            f"{len(risky_events)} download(s) to risky destination(s): {', '.join(dest_types)}. "
            f"Total: {total_bytes / 1e6:.1f} MB. "
            f"{'Destination(s) not seen in baseline.' if new_risky else 'Destination(s) seen before but high-risk.'}"
        ),
        "evidence_event_ids": [e[0] for e in risky_events],
        "observed_value": float(total_bytes),
        "baseline_value": 0.0,
        "why_it_matters": (
            "Downloads to personal devices, USB drives, external shares, or personal email "
            "are common exfiltration vectors. DLP policies should be verified."
        ),
    }]


# ---------------------------------------------------------------------------
# 13. PEER_DEVIATION
# ---------------------------------------------------------------------------
def check_peer_deviation(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
    weights: dict,
) -> list[dict]:
    """Flag when user's behavior significantly deviates from their peer group (role)."""
    if not role_baseline:
        return []

    cfg = get_config()
    z_threshold = cfg.thresholds.peer_deviation_z

    start = datetime.combine(target_date, datetime.min.time()).isoformat()
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()

    # Compare download bytes today vs peer group
    today_bytes_row = conn.execute(
        """SELECT COALESCE(SUM(bytes), 0) FROM download_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end),
    ).fetchone()
    today_bytes = float(today_bytes_row[0]) if today_bytes_row else 0.0

    peer_median = role_baseline.get("download_median_bytes", 0.0)
    peer_mad = max(role_baseline.get("download_mad_bytes", 1.0), 1.0)

    # Robust z-score vs peer group
    peer_z = (today_bytes - peer_median) / (peer_mad / 0.6745)

    deviations = []
    if peer_z >= z_threshold:
        deviations.append(("download_bytes", today_bytes, peer_median, peer_z))

    # Compare file access count
    fa_count_row = conn.execute(
        """SELECT COUNT(*) FROM file_access_events
           WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND is_duplicate = 0""",
        (user_id, start, end),
    ).fetchone()
    fa_count = float(fa_count_row[0]) if fa_count_row else 0.0

    peer_fa_median = role_baseline.get("file_access_median", 0.0)
    peer_fa_mad = max(1.0, peer_fa_median * 0.5)  # fallback MAD estimate
    fa_z = (fa_count - peer_fa_median) / (peer_fa_mad / 0.6745) if peer_fa_mad > 0 else 0.0

    if fa_z >= z_threshold:
        deviations.append(("file_access_count", fa_count, peer_fa_median, fa_z))

    if not deviations:
        return []

    base_pts = _weight(weights, "PEER_DEVIATION", 25)
    top_dev = max(deviations, key=lambda x: x[3])
    severity = min(base_pts, int(base_pts * top_dev[3] / (z_threshold * 2)))
    if severity < base_pts // 2:
        severity = base_pts // 2

    dev_descriptions = [
        f"{d[0]}: observed={d[1]:.1f}, peer median={d[2]:.1f}, z={d[3]:.1f}"
        for d in deviations
    ]

    return [{
        "indicator_id": f"PEER_DEVIATION_{user_id}_{target_date}",
        "name": "PEER_DEVIATION",
        "severity_points": severity,
        "confidence": round(min(1.0, top_dev[3] / (z_threshold * 2)), 2),
        "description": (
            f"User's behavior deviates significantly from peers with same role. "
            f"Deviations: {'; '.join(dev_descriptions)}."
        ),
        "evidence_event_ids": [],
        "observed_value": round(top_dev[1], 1),
        "baseline_value": round(top_dev[2], 1),
        "why_it_matters": (
            "Deviating from peer group behavior adds contextual evidence to other signals. "
            "A user downloading 10x more than any peer on the same day warrants investigation."
        ),
    }]


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------
def compute_indicators(
    conn: sqlite3.Connection,
    user_id: str,
    target_date: date,
    baseline: dict,
    role_baseline: dict,
) -> list[dict]:
    """
    Run all indicator checks for a user on target_date.
    Returns list of indicator dicts (may be empty).
    """
    weights = load_scoring_weights()

    checkers = [
        check_unusual_hour,
        check_new_country,
        check_new_city,
        check_impossible_travel,
        check_new_device,
        check_failed_login_burst_then_success,
        check_download_volume_spike,
        check_download_trend,
        check_new_resource_access,
        check_out_of_role_sensitive_access,
        check_off_hours_privilege_use,
        check_privilege_escalation_sequence,
        check_risky_destination,
        check_peer_deviation,
    ]

    results = []
    for checker in checkers:
        try:
            found = checker(conn, user_id, target_date, baseline, role_baseline, weights)
            if found:
                results.extend(found)
        except Exception as exc:
            # Never let one indicator failure crash the pipeline
            results.append({
                "indicator_id": f"ERROR_{checker.__name__}_{user_id}_{target_date}",
                "name": f"ERROR_{checker.__name__}",
                "severity_points": 0,
                "confidence": 0.0,
                "description": f"Indicator check failed: {exc}",
                "evidence_event_ids": [],
                "observed_value": 0.0,
                "baseline_value": 0.0,
                "why_it_matters": "Internal error — check logs.",
            })

    return results
