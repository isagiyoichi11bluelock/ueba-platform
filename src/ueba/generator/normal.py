"""Normal behaviour event generator for UEBA synthetic dataset.

Generates realistic baseline events (logins, file accesses, downloads,
privilege use) for each user according to their role, typical working hours,
and home location. Includes realistic noise: failed logins, VPN location
variance, duplicate events, and missing optional fields.
"""
from __future__ import annotations

import math
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from .org import OrgStructure, User, PRIVATE_IP_PREFIXES, CITY_COORDS, COUNTRIES_BY_CITY

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOWNLOAD_ROLES = {"Developer", "Finance", "Sales"}
PRIVILEGE_ROLES = {"IT Admin"}


def _rand_ip(rng: random.Random, prefix: str | None = None) -> str:
    """Generate a random IP from RFC 5737 / private ranges."""
    if prefix is None:
        prefix = rng.choice(PRIVATE_IP_PREFIXES)
    # Fill remaining octets
    parts = prefix.rstrip(".").split(".")
    while len(parts) < 4:
        parts.append(str(rng.randint(1, 254)))
    return ".".join(parts[:4])


def _city_ip_prefix(city: str, rng: random.Random) -> str:
    """Return a deterministic-ish IP prefix for a city (fake, RFC 5737)."""
    # Map city to a stable prefix using its index
    cities = list(CITY_COORDS.keys())
    idx = cities.index(city) if city in cities else 0
    prefixes = PRIVATE_IP_PREFIXES
    return prefixes[idx % len(prefixes)]


def _make_event_id(table_prefix: str) -> str:
    return f"{table_prefix}-{uuid.uuid4().hex[:8].upper()}"


def _ts(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _login_time(user: User, day: date, rng: random.Random) -> datetime:
    """Return login datetime for user on given day with realistic variance."""
    base_hour = user.work_start_hour
    # Add variance: -15 to +30 min
    minute_offset = rng.randint(-15, 30)
    dt = datetime(day.year, day.month, day.day, base_hour, 0) + timedelta(minutes=minute_offset)
    return dt


def _user_home_ip(user: User, rng: random.Random) -> str:
    prefix = _city_ip_prefix(user.home_city, rng)
    return _rand_ip(rng, prefix)


def _vpn_city(user: User, rng: random.Random) -> tuple[str, str]:
    """Return (city, country) for VPN-driven location noise (same country, different city)."""
    same_country = [
        c for c, country in COUNTRIES_BY_CITY.items()
        if country == user.home_country and c != user.home_city
    ]
    if same_country:
        city = rng.choice(same_country)
        return city, user.home_country
    return user.home_city, user.home_country


def _work_hours_in_day(user: User) -> tuple[int, int]:
    start = user.work_start_hour
    end = user.work_end_hour
    if end <= start:  # night shift wraps midnight
        end = start + 8
    return start, end


def _random_time_in_shift(user: User, day: date, rng: random.Random) -> datetime:
    """Return a random datetime within the user's shift on the given day."""
    start_h, end_h = _work_hours_in_day(user)
    minutes_in_shift = max(1, (end_h - start_h) * 60)
    offset_minutes = rng.randint(0, minutes_in_shift)
    return datetime(day.year, day.month, day.day, start_h, 0) + timedelta(minutes=offset_minutes)


def _lognormal_bytes(rng: random.Random, mean_mb: float = 50, sigma: float = 1.2) -> int:
    """Return a log-normal random byte count."""
    mb = math.exp(rng.gauss(math.log(mean_mb), sigma))
    return max(1024, int(mb * 1024 * 1024))


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_normal_events(
    org: OrgStructure,
    context_events: list,
    start_date: date,
    end_date: date,
    seed: int = 42,
) -> dict[str, list[dict]]:
    """
    Generate normal (non-scenario) events for all users over the specified date range.

    Returns a dict with keys:
        login_events, file_access_events, download_events, privilege_events
    """
    rng = random.Random(seed + 200)

    login_events: list[dict] = []
    file_access_events: list[dict] = []
    download_events: list[dict] = []
    privilege_events: list[dict] = []

    # Build lookup: user_id -> context events
    user_ctx: dict[str, list] = {u.user_id: [] for u in org.users}
    for ce in context_events:
        if ce.user_id in user_ctx:
            user_ctx[ce.user_id].append(ce)

    # Resources by role
    role_allowed = org.role_allowed_resources
    role_typical = org.role_typical_resources

    # Per-user download baseline (log-normal per-user mean, in MB)
    user_dl_mean: dict[str, float] = {}
    for user in org.users:
        if user.role in DOWNLOAD_ROLES:
            user_dl_mean[user.user_id] = math.exp(rng.gauss(math.log(30), 0.5))

    total_days = (end_date - start_date).days + 1

    for user in org.users:
        # Per-user sub-RNG for reproducibility
        user_seed = seed + hash(user.user_id) & 0xFFFFFF
        urng = random.Random(user_seed)

        allowed_res = role_allowed.get(user.role, [])
        typical_res = role_typical.get(user.role, [])
        if not allowed_res:
            allowed_res = ["RES-0001"]
        if not typical_res:
            typical_res = allowed_res[:5] if allowed_res else ["RES-0001"]

        for day_offset in range(total_days):
            current_day = start_date + timedelta(days=day_offset)
            weekday = current_day.weekday()  # 0=Mon

            # Determine if user works today
            is_working_day = weekday in user.working_days
            # Weekend work: 10% chance for employees
            weekend_work = False
            if not is_working_day and weekday in (5, 6):
                weekend_work = urng.random() < 0.10

            if not is_working_day and not weekend_work:
                continue

            # Finance month-end: check for month_end_close context
            is_month_end = False
            for ce in user_ctx[user.user_id]:
                if ce.context_type == "month_end_close":
                    if ce.start_time.date() <= current_day <= ce.end_time.date():
                        is_month_end = True

            # ----- LOGIN EVENTS -----
            session_id = str(uuid.uuid4())
            login_dt = _login_time(user, current_day, urng)

            # VPN location noise (~5%)
            use_vpn = urng.random() < 0.05
            if use_vpn:
                login_city, login_country = _vpn_city(user, urng)
                login_ip = _rand_ip(urng)
            else:
                login_city = user.home_city
                login_country = user.home_country
                login_ip = _user_home_ip(user, urng)

            login_device = urng.choice(user.devices)

            # Failed logins (~5% of days have 1-2 failed attempts first)
            if urng.random() < 0.05:
                fail_count = urng.randint(1, 2)
                for _ in range(fail_count):
                    fail_id = _make_event_id("LGN")
                    fail_dt = login_dt - timedelta(minutes=urng.randint(1, 5))
                    fail_ev: dict[str, Any] = {
                        "event_id": fail_id,
                        "timestamp": _ts(fail_dt),
                        "user_id": user.user_id,
                        "source_ip": login_ip,
                        "country": login_country,
                        "city": login_city,
                        "device_id": login_device,
                        "auth_result": "failure",
                        "auth_method": "password",
                        "session_id": "",
                        "is_duplicate": False,
                    }
                    login_events.append(fail_ev)

            # Successful login
            login_ev: dict[str, Any] = {
                "event_id": _make_event_id("LGN"),
                "timestamp": _ts(login_dt),
                "user_id": user.user_id,
                "source_ip": login_ip,
                "country": login_country,
                "city": login_city,
                "device_id": login_device,
                "auth_result": "success",
                "auth_method": "password",
                "session_id": session_id,
                "is_duplicate": False,
            }
            # ~0.5% duplicate events
            if urng.random() < 0.005:
                login_ev["is_duplicate"] = True

            # ~0.3% missing optional field (city)
            if urng.random() < 0.003:
                login_ev["city"] = ""

            login_events.append(login_ev)

            # ----- FILE ACCESS EVENTS -----
            # Events per day: 5-50 based on role, more for month-end Finance
            base_count = {
                "Developer": urng.randint(15, 35),
                "Finance": urng.randint(20, 40),
                "HR": urng.randint(10, 25),
                "Sales": urng.randint(12, 30),
                "IT Admin": urng.randint(8, 20),
                "Contractor": urng.randint(5, 15),
            }.get(user.role, urng.randint(5, 20))

            if is_month_end and user.role == "Finance":
                base_count = int(base_count * 2.5)

            # Choose resources: mostly typical, sometimes from allowed pool
            for _ in range(base_count):
                use_typical = urng.random() < 0.75
                if use_typical and typical_res:
                    res_id = urng.choice(typical_res)
                elif allowed_res:
                    res_id = urng.choice(allowed_res)
                else:
                    res_id = "RES-0001"

                action = urng.choice(["read", "read", "read", "write", "list"])
                fa_dt = _random_time_in_shift(user, current_day, urng)
                fa_ev: dict[str, Any] = {
                    "event_id": _make_event_id("FAC"),
                    "timestamp": _ts(fa_dt),
                    "user_id": user.user_id,
                    "session_id": session_id,
                    "resource_id": res_id,
                    "action": action,
                    "result": "success",
                    "is_duplicate": False,
                }
                # ~0.5% duplicates
                if urng.random() < 0.005:
                    fa_ev["is_duplicate"] = True
                # ~0.3% missing result
                if urng.random() < 0.003:
                    fa_ev["result"] = ""
                file_access_events.append(fa_ev)

            # ----- DOWNLOAD EVENTS -----
            if user.role in DOWNLOAD_ROLES:
                dl_count = urng.randint(1, 5)
                if is_month_end and user.role == "Finance":
                    dl_count = urng.randint(5, 12)

                mean_mb = user_dl_mean.get(user.user_id, 30)
                for _ in range(dl_count):
                    if typical_res:
                        res_id = urng.choice(typical_res)
                    else:
                        res_id = urng.choice(allowed_res) if allowed_res else "RES-0001"

                    dl_dt = _random_time_in_shift(user, current_day, urng)
                    dl_bytes = _lognormal_bytes(urng, mean_mb=mean_mb)
                    dl_ev: dict[str, Any] = {
                        "event_id": _make_event_id("DL"),
                        "timestamp": _ts(dl_dt),
                        "user_id": user.user_id,
                        "session_id": session_id,
                        "resource_id": res_id,
                        "bytes": dl_bytes,
                        "file_count": urng.randint(1, 5),
                        "destination_type": "managed_laptop",
                        "is_duplicate": False,
                    }
                    if urng.random() < 0.005:
                        dl_ev["is_duplicate"] = True
                    download_events.append(dl_ev)

            # ----- PRIVILEGE EVENTS -----
            if user.role in PRIVILEGE_ROLES:
                priv_count = urng.randint(1, 5)
                priv_actions = ["sudo", "config_change", "user_create", "log_read", "service_restart"]
                priv_targets = ["server01", "server02", "firewall", "ldap", "monitoring", "backup"]

                for _ in range(priv_count):
                    priv_dt = _random_time_in_shift(user, current_day, urng)
                    pev: dict[str, Any] = {
                        "event_id": _make_event_id("PRV"),
                        "timestamp": _ts(priv_dt),
                        "user_id": user.user_id,
                        "session_id": session_id,
                        "action": urng.choice(priv_actions),
                        "target": urng.choice(priv_targets),
                        "result": "success",
                        "is_duplicate": False,
                    }
                    if urng.random() < 0.005:
                        pev["is_duplicate"] = True
                    privilege_events.append(pev)

    return {
        "login_events": login_events,
        "file_access_events": file_access_events,
        "download_events": download_events,
        "privilege_events": privilege_events,
    }
