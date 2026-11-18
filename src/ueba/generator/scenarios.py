"""Inject 8 UEBA detection scenarios into the detection period (days 76-90).

Scenarios:
  S1 - Compromised credentials (Developer)
  S2 - Departing employee data hoarding (Sales)
  S3 - Contractor scope creep
  S4 - Benign approved travel (Finance, WITH context)
  S5 - Benign month-end close (Finance, WITH context)
  S6 - Benign new joiner (new user, only 5 days history)
  S7 - Benign on-call IT admin
  S8 - No-context travel (same as S4 but NO context event)
"""
from __future__ import annotations

import math
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from .org import (
    OrgStructure, User,
    PRIVATE_IP_PREFIXES, CITY_COORDS, COUNTRIES_BY_CITY,
    RESOURCE_TYPES_BY_ROLE,
)
from .context import ContextEvent

# ---------------------------------------------------------------------------
# Helpers (duplicated to keep module self-contained)
# ---------------------------------------------------------------------------

def _rand_ip(rng: random.Random, prefix: str | None = None) -> str:
    if prefix is None:
        prefix = rng.choice(PRIVATE_IP_PREFIXES)
    parts = prefix.rstrip(".").split(".")
    while len(parts) < 4:
        parts.append(str(rng.randint(1, 254)))
    return ".".join(parts[:4])


def _foreign_ip(rng: random.Random) -> str:
    """Return an IP that looks like a foreign/cloud host (still RFC 5737)."""
    # Use 198.51.100.x as 'external' range
    return f"198.51.100.{rng.randint(10, 240)}"


def _make_event_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _ts(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _lognormal_bytes(rng: random.Random, mean_mb: float = 200.0, sigma: float = 0.8) -> int:
    mb = math.exp(rng.gauss(math.log(mean_mb), sigma))
    return max(1024 * 1024, int(mb * 1024 * 1024))


def _get_detection_window(start_date: date, num_days: int = 90) -> tuple[date, date]:
    """Return (detection_start, detection_end) = days 76-90."""
    detection_start = start_date + timedelta(days=75)  # day 76 (0-indexed)
    detection_end = start_date + timedelta(days=num_days - 1)  # day 90
    return detection_start, detection_end


def _find_user(org: OrgStructure, role: str, exclude_ids: set[str] | None = None) -> User | None:
    candidates = [u for u in org.users if u.role == role]
    if exclude_ids:
        candidates = [u for u in candidates if u.user_id not in exclude_ids]
    return candidates[0] if candidates else None


def _restricted_resources(org: OrgStructure) -> list[str]:
    return [r.resource_id for r in org.resources if r.sensitivity == "Restricted"]


def _out_of_role_resources(org: OrgStructure, role: str) -> list[str]:
    """Resources that are sensitive and NOT in this role's allowed set."""
    allowed = set(org.role_allowed_resources.get(role, []))
    return [r.resource_id for r in org.resources
            if r.resource_id not in allowed and r.sensitivity in ("Confidential", "Restricted")]


# ---------------------------------------------------------------------------
# S1: Compromised credentials
# ---------------------------------------------------------------------------

def _scenario_s1(org: OrgStructure, start_date: date, end_date: date, rng: random.Random) -> dict:
    """
    Compromised Developer credentials.
    - 8 failed logins in 5 minutes from home IP
    - Then success from foreign country/new device at 03:00 UTC
    - Privilege escalation (role_grant + admin_command)
    - Bulk download: 15 Restricted resources, 2GB to external_share
    Expected score >= 80.
    """
    detection_start, detection_end = _get_detection_window(start_date)
    # Pick attack day ~day 80
    attack_day = detection_start + timedelta(days=rng.randint(2, 8))

    dev_user = _find_user(org, "Developer")
    if dev_user is None:
        return {}

    logins = []
    files = []
    downloads = []
    privileges = []
    ground_truth = []

    attacker_ip = _foreign_ip(rng)
    attacker_device = f"DEV-UNKNOWN-{uuid.uuid4().hex[:6].upper()}"
    attacker_country = rng.choice(["GB", "JP", "CN", "RU"])
    attacker_city = rng.choice(["London", "Tokyo", "Shanghai", "Berlin"])
    # Keep in CITY_COORDS if possible
    if attacker_city not in CITY_COORDS:
        attacker_city = "London"

    home_ip = f"10.0.{rng.randint(1,50)}.{rng.randint(1,254)}"
    attack_time = datetime(attack_day.year, attack_day.month, attack_day.day, 3, 0, 0)

    # 8 failed logins from home IP in 5 minutes (looks like credential stuffing from home then attacker)
    for i in range(8):
        fail_dt = attack_time - timedelta(minutes=5) + timedelta(seconds=i * 35)
        logins.append({
            "event_id": _make_event_id("LGN"),
            "timestamp": _ts(fail_dt),
            "user_id": dev_user.user_id,
            "source_ip": home_ip,
            "country": dev_user.home_country,
            "city": dev_user.home_city,
            "device_id": dev_user.devices[0] if dev_user.devices else attacker_device,
            "auth_result": "failure",
            "auth_method": "password",
            "session_id": "",
            "is_duplicate": False,
        })

    # Successful login from foreign country on new device
    attacker_session = str(uuid.uuid4())
    logins.append({
        "event_id": _make_event_id("LGN"),
        "timestamp": _ts(attack_time),
        "user_id": dev_user.user_id,
        "source_ip": attacker_ip,
        "country": attacker_country,
        "city": attacker_city,
        "device_id": attacker_device,
        "auth_result": "success",
        "auth_method": "password",
        "session_id": attacker_session,
        "is_duplicate": False,
    })

    # Privilege escalation
    for action, target in [("role_grant", "admin"), ("admin_command", "shadow_copy")]:
        priv_dt = attack_time + timedelta(minutes=rng.randint(2, 10))
        privileges.append({
            "event_id": _make_event_id("PRV"),
            "timestamp": _ts(priv_dt),
            "user_id": dev_user.user_id,
            "session_id": attacker_session,
            "action": action,
            "target": target,
            "result": "success",
            "is_duplicate": False,
        })

    # Bulk download: 15 Restricted resources, 2GB to external_share
    restricted = _restricted_resources(org)
    if len(restricted) < 15:
        restricted = restricted * 3  # pad if few restricted resources
    chosen_res = rng.sample(restricted, min(15, len(restricted)))
    total_bytes = 2 * 1024 * 1024 * 1024  # 2GB
    per_res_bytes = total_bytes // len(chosen_res)
    for i, res_id in enumerate(chosen_res):
        dl_dt = attack_time + timedelta(minutes=15 + i * 2)
        downloads.append({
            "event_id": _make_event_id("DL"),
            "timestamp": _ts(dl_dt),
            "user_id": dev_user.user_id,
            "session_id": attacker_session,
            "resource_id": res_id,
            "bytes": per_res_bytes,
            "file_count": rng.randint(10, 50),
            "destination_type": "external_share",
            "is_duplicate": False,
        })

    ground_truth.append({
        "scenario_id": "S1",
        "user_id": dev_user.user_id,
        "start_time": _ts(attack_time - timedelta(minutes=5)),
        "end_time": _ts(attack_time + timedelta(minutes=50)),
        "label": "TRUE_POSITIVE",
        "description": "Compromised developer credentials: failed login burst, foreign login, privilege escalation, bulk restricted download.",
        "expected_min_score": 80,
        "expected_max_score": 100,
    })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": [],
        "ground_truth": ground_truth,
    }


# ---------------------------------------------------------------------------
# S2: Departing employee data hoarding
# ---------------------------------------------------------------------------

def _scenario_s2(org: OrgStructure, start_date: date, end_date: date, rng: random.Random) -> dict:
    """
    Sales user downloading increasing volumes over 10 days.
    Downloads outside normal Sales resource set + to personal_device.
    Expected score >= 65.
    """
    detection_start, detection_end = _get_detection_window(start_date)
    sales_user = _find_user(org, "Sales")
    if sales_user is None:
        return {}

    logins = []
    files = []
    downloads = []
    privileges: list[dict] = []
    ground_truth = []

    out_of_role_res = _out_of_role_resources(org, "Sales")
    allowed_res = org.role_allowed_resources.get("Sales", [])
    if not out_of_role_res:
        out_of_role_res = ["RES-0100", "RES-0101"]

    base_mb = 50.0  # Starting daily download volume
    for day_idx in range(10):
        current_day = detection_start + timedelta(days=day_idx)
        if current_day > detection_end:
            break

        # Volume doubles every 2 days
        multiplier = 2 ** (day_idx // 2)
        day_mb = base_mb * multiplier

        session_id = str(uuid.uuid4())
        login_dt = datetime(current_day.year, current_day.month, current_day.day,
                            sales_user.work_start_hour, rng.randint(0, 30))
        logins.append({
            "event_id": _make_event_id("LGN"),
            "timestamp": _ts(login_dt),
            "user_id": sales_user.user_id,
            "source_ip": f"10.1.{rng.randint(1,50)}.{rng.randint(1,254)}",
            "country": sales_user.home_country,
            "city": sales_user.home_city,
            "device_id": sales_user.devices[0] if sales_user.devices else "DEV-SALES-01",
            "auth_result": "success",
            "auth_method": "password",
            "session_id": session_id,
            "is_duplicate": False,
        })

        # Accesses resources outside normal Sales set
        for fa_res in rng.sample(out_of_role_res, min(5, len(out_of_role_res))):
            fa_dt = login_dt + timedelta(minutes=rng.randint(5, 60))
            files.append({
                "event_id": _make_event_id("FAC"),
                "timestamp": _ts(fa_dt),
                "user_id": sales_user.user_id,
                "session_id": session_id,
                "resource_id": fa_res,
                "action": "read",
                "result": "success",
                "is_duplicate": False,
            })

        # Increasing downloads to personal_device
        num_downloads = rng.randint(3, 8) * (day_idx // 2 + 1)
        for dl_i in range(num_downloads):
            dl_res = rng.choice(out_of_role_res + allowed_res) if allowed_res else rng.choice(out_of_role_res)
            dl_bytes = int((day_mb / num_downloads) * 1024 * 1024)
            dl_dt = login_dt + timedelta(minutes=rng.randint(10, 240))
            downloads.append({
                "event_id": _make_event_id("DL"),
                "timestamp": _ts(dl_dt),
                "user_id": sales_user.user_id,
                "session_id": session_id,
                "resource_id": dl_res,
                "bytes": dl_bytes,
                "file_count": rng.randint(1, 10),
                "destination_type": "personal_device",
                "is_duplicate": False,
            })

    ground_truth.append({
        "scenario_id": "S2",
        "user_id": sales_user.user_id,
        "start_time": _ts(datetime.combine(detection_start, datetime.min.time())),
        "end_time": _ts(datetime.combine(detection_start + timedelta(days=9), datetime.max.time().replace(microsecond=0))),
        "label": "TRUE_POSITIVE",
        "description": "Departing Sales employee hoarding data: escalating download volume over 10 days, out-of-role access, personal device destination.",
        "expected_min_score": 65,
        "expected_max_score": 100,
    })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": [],
        "ground_truth": ground_truth,
    }


# ---------------------------------------------------------------------------
# S3: Contractor scope creep
# ---------------------------------------------------------------------------

def _scenario_s3(org: OrgStructure, start_date: date, end_date: date, rng: random.Random) -> dict:
    """
    Contractor reads HR and Finance Restricted resources outside their role scope.
    Accesses during off-hours (00:00-05:00).
    Expected score >= 55.
    """
    detection_start, detection_end = _get_detection_window(start_date)
    contractor = _find_user(org, "Contractor")
    if contractor is None:
        return {}

    logins = []
    files = []
    downloads: list[dict] = []
    privileges: list[dict] = []
    ground_truth = []

    # Find HR and Finance Restricted resources
    hr_finance_res = [
        r.resource_id for r in org.resources
        if r.resource_type in ("hr_records", "payroll_db", "finance_ledger")
        and r.sensitivity in ("Confidential", "Restricted")
    ]
    if not hr_finance_res:
        hr_finance_res = ["RES-0050", "RES-0051", "RES-0052"]

    # 5 off-hours incursion days
    incursion_days = rng.sample(
        list(range((detection_end - detection_start).days + 1)),
        min(5, (detection_end - detection_start).days + 1)
    )

    for day_offset in incursion_days:
        current_day = detection_start + timedelta(days=day_offset)
        off_hour = rng.randint(0, 4)  # 00:00-04:59
        attack_dt = datetime(current_day.year, current_day.month, current_day.day, off_hour, rng.randint(0, 59))

        session_id = str(uuid.uuid4())
        logins.append({
            "event_id": _make_event_id("LGN"),
            "timestamp": _ts(attack_dt),
            "user_id": contractor.user_id,
            "source_ip": _rand_ip(rng),
            "country": contractor.home_country,
            "city": contractor.home_city,
            "device_id": contractor.devices[0] if contractor.devices else "DEV-CTR-01",
            "auth_result": "success",
            "auth_method": "password",
            "session_id": session_id,
            "is_duplicate": False,
        })

        # Access HR/Finance restricted resources
        for res_id in rng.sample(hr_finance_res, min(4, len(hr_finance_res))):
            fa_dt = attack_dt + timedelta(minutes=rng.randint(2, 20))
            files.append({
                "event_id": _make_event_id("FAC"),
                "timestamp": _ts(fa_dt),
                "user_id": contractor.user_id,
                "session_id": session_id,
                "resource_id": res_id,
                "action": "read",
                "result": "success",
                "is_duplicate": False,
            })

    ground_truth.append({
        "scenario_id": "S3",
        "user_id": contractor.user_id,
        "start_time": _ts(datetime.combine(detection_start, datetime.min.time())),
        "end_time": _ts(datetime.combine(detection_end, datetime.max.time().replace(microsecond=0))),
        "label": "TRUE_POSITIVE",
        "description": "Contractor accessing HR/Finance restricted resources during off-hours (00:00-05:00), outside permitted scope.",
        "expected_min_score": 55,
        "expected_max_score": 100,
    })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": [],
        "ground_truth": ground_truth,
    }


# ---------------------------------------------------------------------------
# S4: Benign approved travel (Finance, WITH context event)
# ---------------------------------------------------------------------------

def _scenario_s4(org: OrgStructure, start_date: date, end_date: date,
                 rng: random.Random, existing_user_ids: set[str]) -> dict:
    """
    Finance user travels to foreign country.
    Unusual hours, new device — but HAS an approved_travel context event.
    Expected score <= 35.
    """
    detection_start, detection_end = _get_detection_window(start_date)
    finance_user = _find_user(org, "Finance", exclude_ids=existing_user_ids)
    if finance_user is None:
        finance_user = _find_user(org, "Finance")
    if finance_user is None:
        return {}

    logins = []
    files = []
    downloads: list[dict] = []
    privileges: list[dict] = []
    context_events = []
    ground_truth = []

    travel_city = "London"
    travel_country = "GB"
    travel_ip = f"203.0.113.{rng.randint(1, 200)}"
    travel_device = finance_user.devices[0] if finance_user.devices else "DEV-FINANCE-01"

    travel_start = detection_start + timedelta(days=1)
    travel_end = travel_start + timedelta(days=4)

    # Context event: approved travel
    context_events.append(ContextEvent(
        context_id=str(uuid.uuid4()),
        user_id=finance_user.user_id,
        context_type="approved_travel",
        start_time=datetime.combine(travel_start, datetime.min.time()),
        end_time=datetime.combine(min(travel_end, detection_end), datetime.max.time().replace(microsecond=0)),
        approved_by_role="Manager",
        notes="Approved travel to London for client meeting",
    ))

    # Logins from London
    for day_offset in range(5):
        current_day = travel_start + timedelta(days=day_offset)
        if current_day > detection_end:
            break
        # Unusual hour in home timezone (but reasonable in London)
        login_dt = datetime(current_day.year, current_day.month, current_day.day,
                            rng.randint(6, 10), rng.randint(0, 59))
        session_id = str(uuid.uuid4())
        logins.append({
            "event_id": _make_event_id("LGN"),
            "timestamp": _ts(login_dt),
            "user_id": finance_user.user_id,
            "source_ip": travel_ip,
            "country": travel_country,
            "city": travel_city,
            "device_id": travel_device,
            "auth_result": "success",
            "auth_method": "password",
            "session_id": session_id,
            "is_duplicate": False,
        })
        # Normal file access
        allowed_res = org.role_allowed_resources.get("Finance", [])
        for _ in range(rng.randint(5, 15)):
            if allowed_res:
                fa_dt = login_dt + timedelta(minutes=rng.randint(5, 60))
                files.append({
                    "event_id": _make_event_id("FAC"),
                    "timestamp": _ts(fa_dt),
                    "user_id": finance_user.user_id,
                    "session_id": session_id,
                    "resource_id": rng.choice(allowed_res),
                    "action": "read",
                    "result": "success",
                    "is_duplicate": False,
                })

    ground_truth.append({
        "scenario_id": "S4",
        "user_id": finance_user.user_id,
        "start_time": _ts(datetime.combine(travel_start, datetime.min.time())),
        "end_time": _ts(datetime.combine(min(travel_end, detection_end), datetime.max.time().replace(microsecond=0))),
        "label": "BENIGN_EXPLAINED",
        "description": "Finance user travelling with approved context: foreign login is explained by approved_travel event.",
        "expected_min_score": 0,
        "expected_max_score": 35,
    })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": context_events,
        "ground_truth": ground_truth,
    }


# ---------------------------------------------------------------------------
# S5: Benign month-end close (Finance team WITH context)
# ---------------------------------------------------------------------------

def _scenario_s5(org: OrgStructure, start_date: date, end_date: date, rng: random.Random) -> dict:
    """
    Finance users download 8x normal volume on last 3 days of detection period.
    Has month_end_close context event.
    Expected score <= 35.
    """
    detection_start, detection_end = _get_detection_window(start_date)

    # Last 3 days of detection period
    close_start = detection_end - timedelta(days=2)
    finance_users = [u for u in org.users if u.role == "Finance"][:3]  # pick 3 Finance users

    logins = []
    files = []
    downloads = []
    privileges: list[dict] = []
    context_events_list = []
    ground_truth = []

    for finance_user in finance_users:
        # Context event: month_end_close
        context_events_list.append(ContextEvent(
            context_id=str(uuid.uuid4()),
            user_id=finance_user.user_id,
            context_type="month_end_close",
            start_time=datetime.combine(close_start, datetime.min.time()),
            end_time=datetime.combine(detection_end, datetime.max.time().replace(microsecond=0)),
            approved_by_role="Finance Manager",
            notes="Scheduled month-end financial close (scenario context)",
        ))

        allowed_res = org.role_allowed_resources.get("Finance", [])
        typical_res = org.role_typical_resources.get("Finance", [])

        for day_offset in range(3):
            current_day = close_start + timedelta(days=day_offset)
            if current_day > detection_end:
                break

            session_id = str(uuid.uuid4())
            login_dt = datetime(current_day.year, current_day.month, current_day.day,
                                finance_user.work_start_hour, rng.randint(0, 20))
            logins.append({
                "event_id": _make_event_id("LGN"),
                "timestamp": _ts(login_dt),
                "user_id": finance_user.user_id,
                "source_ip": f"192.168.1.{rng.randint(10, 200)}",
                "country": finance_user.home_country,
                "city": finance_user.home_city,
                "device_id": finance_user.devices[0] if finance_user.devices else "DEV-FIN-01",
                "auth_result": "success",
                "auth_method": "password",
                "session_id": session_id,
                "is_duplicate": False,
            })

            # 8x normal file access
            for _ in range(rng.randint(60, 100)):
                res_id = rng.choice(typical_res) if typical_res else rng.choice(allowed_res) if allowed_res else "RES-0001"
                fa_dt = login_dt + timedelta(minutes=rng.randint(2, 480))
                files.append({
                    "event_id": _make_event_id("FAC"),
                    "timestamp": _ts(fa_dt),
                    "user_id": finance_user.user_id,
                    "session_id": session_id,
                    "resource_id": res_id,
                    "action": rng.choice(["read", "write"]),
                    "result": "success",
                    "is_duplicate": False,
                })

            # 8x normal downloads (~400MB/day)
            for _ in range(rng.randint(15, 25)):
                res_id = rng.choice(typical_res) if typical_res else "RES-0001"
                dl_bytes = int(rng.uniform(10, 50) * 1024 * 1024)
                dl_dt = login_dt + timedelta(minutes=rng.randint(5, 420))
                downloads.append({
                    "event_id": _make_event_id("DL"),
                    "timestamp": _ts(dl_dt),
                    "user_id": finance_user.user_id,
                    "session_id": session_id,
                    "resource_id": res_id,
                    "bytes": dl_bytes,
                    "file_count": rng.randint(1, 20),
                    "destination_type": "managed_laptop",
                    "is_duplicate": False,
                })

        ground_truth.append({
            "scenario_id": "S5",
            "user_id": finance_user.user_id,
            "start_time": _ts(datetime.combine(close_start, datetime.min.time())),
            "end_time": _ts(datetime.combine(detection_end, datetime.max.time().replace(microsecond=0))),
            "label": "BENIGN_EXPLAINED",
            "description": "Finance month-end close: high download/access volume explained by month_end_close context event.",
            "expected_min_score": 0,
            "expected_max_score": 35,
        })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": context_events_list,
        "ground_truth": ground_truth,
    }


# ---------------------------------------------------------------------------
# S6: Benign new joiner
# ---------------------------------------------------------------------------

def _scenario_s6(org: OrgStructure, start_date: date, end_date: date, rng: random.Random) -> dict:
    """
    New user with only 5 days of history — broad exploratory access.
    Low baseline confidence (new user) => score <= 45.
    """
    detection_start, detection_end = _get_detection_window(start_date)

    # Create a synthetic new user (not in org, only 5 days history)
    new_user_id = "E0999"
    new_user_start = detection_end - timedelta(days=4)  # Only 5 days history

    logins = []
    files = []
    downloads: list[dict] = []
    privileges: list[dict] = []
    context_events_list = []
    ground_truth = []

    # Context: new_joiner
    context_events_list.append(ContextEvent(
        context_id=str(uuid.uuid4()),
        user_id=new_user_id,
        context_type="new_joiner",
        start_time=datetime.combine(new_user_start, datetime.min.time()),
        end_time=datetime.combine(detection_end, datetime.max.time().replace(microsecond=0)),
        approved_by_role="HR Manager",
        notes="New employee onboarding period",
    ))

    # Also add this user to org users (temporarily) by using existing org resources
    all_res = [r.resource_id for r in org.resources]

    for day_offset in range(5):
        current_day = new_user_start + timedelta(days=day_offset)
        if current_day > detection_end:
            break

        session_id = str(uuid.uuid4())
        login_dt = datetime(current_day.year, current_day.month, current_day.day,
                            rng.randint(8, 10), rng.randint(0, 59))
        logins.append({
            "event_id": _make_event_id("LGN"),
            "timestamp": _ts(login_dt),
            "user_id": new_user_id,
            "source_ip": f"10.0.{rng.randint(1, 50)}.{rng.randint(1, 254)}",
            "country": "US",
            "city": "New York",
            "device_id": f"DEV-{new_user_id}-1",
            "auth_result": "success",
            "auth_method": "password",
            "session_id": session_id,
            "is_duplicate": False,
        })

        # Broad exploratory access (many different resources)
        sampled_res = rng.sample(all_res, min(20, len(all_res)))
        for res_id in sampled_res:
            fa_dt = login_dt + timedelta(minutes=rng.randint(5, 240))
            files.append({
                "event_id": _make_event_id("FAC"),
                "timestamp": _ts(fa_dt),
                "user_id": new_user_id,
                "session_id": session_id,
                "resource_id": res_id,
                "action": "read",
                "result": "success",
                "is_duplicate": False,
            })

    ground_truth.append({
        "scenario_id": "S6",
        "user_id": new_user_id,
        "start_time": _ts(datetime.combine(new_user_start, datetime.min.time())),
        "end_time": _ts(datetime.combine(detection_end, datetime.max.time().replace(microsecond=0))),
        "label": "BENIGN_EXPLAINED",
        "description": "New joiner with only 5 days of history: broad exploratory access is expected; low baseline confidence dampens score.",
        "expected_min_score": 0,
        "expected_max_score": 45,
    })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": context_events_list,
        "ground_truth": ground_truth,
        "extra_users": [{
            "user_id": new_user_id,
            "role": "Developer",
            "department": "Engineering",
            "home_country": "US",
            "home_city": "New York",
            "devices": [f"DEV-{new_user_id}-1"],
            "hire_date": new_user_start.isoformat(),
            "work_start_hour": 9,
            "work_end_hour": 17,
            "timezone": "US/Eastern",
            "working_days": [0, 1, 2, 3, 4],
            "is_manager": False,
            "is_contractor": False,
            "is_night_shift": False,
            "is_part_time": False,
        }],
    }


# ---------------------------------------------------------------------------
# S7: Benign on-call IT admin
# ---------------------------------------------------------------------------

def _scenario_s7(org: OrgStructure, start_date: date, end_date: date, rng: random.Random) -> dict:
    """
    IT Admin uses sudo/admin commands at 02:00.
    Has on_call context event.
    Expected score <= 35.
    """
    detection_start, detection_end = _get_detection_window(start_date)
    it_user = _find_user(org, "IT Admin")
    if it_user is None:
        return {}

    logins = []
    files: list[dict] = []
    downloads: list[dict] = []
    privileges = []
    context_events_list = []
    ground_truth = []

    on_call_day = detection_start + timedelta(days=rng.randint(0, 5))

    # Context: on_call
    context_events_list.append(ContextEvent(
        context_id=str(uuid.uuid4()),
        user_id=it_user.user_id,
        context_type="on_call",
        start_time=datetime.combine(on_call_day, datetime.min.time()),
        end_time=datetime.combine(on_call_day, datetime.max.time().replace(microsecond=0)),
        approved_by_role="IT Manager",
        notes="Emergency on-call shift — scenario context",
    ))

    # Login at 02:00
    oncall_dt = datetime(on_call_day.year, on_call_day.month, on_call_day.day, 2, rng.randint(0, 30))
    session_id = str(uuid.uuid4())
    logins.append({
        "event_id": _make_event_id("LGN"),
        "timestamp": _ts(oncall_dt),
        "user_id": it_user.user_id,
        "source_ip": f"192.168.2.{rng.randint(1, 254)}",
        "country": it_user.home_country,
        "city": it_user.home_city,
        "device_id": it_user.devices[0] if it_user.devices else "DEV-IT-01",
        "auth_result": "success",
        "auth_method": "password",
        "session_id": session_id,
        "is_duplicate": False,
    })

    # Sudo and admin commands
    for action, target in [
        ("sudo", "service_restart"),
        ("admin_command", "log_analysis"),
        ("config_change", "firewall"),
    ]:
        priv_dt = oncall_dt + timedelta(minutes=rng.randint(5, 30))
        privileges.append({
            "event_id": _make_event_id("PRV"),
            "timestamp": _ts(priv_dt),
            "user_id": it_user.user_id,
            "session_id": session_id,
            "action": action,
            "target": target,
            "result": "success",
            "is_duplicate": False,
        })

    ground_truth.append({
        "scenario_id": "S7",
        "user_id": it_user.user_id,
        "start_time": _ts(oncall_dt),
        "end_time": _ts(oncall_dt + timedelta(hours=2)),
        "label": "BENIGN_EXPLAINED",
        "description": "IT Admin running privileged commands at 02:00 during approved on-call shift.",
        "expected_min_score": 0,
        "expected_max_score": 35,
    })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": context_events_list,
        "ground_truth": ground_truth,
    }


# ---------------------------------------------------------------------------
# S8: No-context travel (same as S4 but NO approved_travel context)
# ---------------------------------------------------------------------------

def _scenario_s8(org: OrgStructure, start_date: date, end_date: date,
                 rng: random.Random, existing_user_ids: set[str]) -> dict:
    """
    Finance user logs in from new country, unusual hours, new device — NO context event.
    Expected score >= 60 (HIGH).
    """
    detection_start, detection_end = _get_detection_window(start_date)
    # Pick a Finance user different from S4
    finance_user = _find_user(org, "Finance", exclude_ids=existing_user_ids)
    if finance_user is None:
        # Reuse any Finance user
        finance_user = _find_user(org, "Finance")
    if finance_user is None:
        return {}

    logins = []
    files = []
    downloads: list[dict] = []
    privileges: list[dict] = []
    ground_truth = []

    travel_city = "Tokyo"
    travel_country = "JP"
    travel_ip = f"198.51.100.{rng.randint(50, 240)}"
    new_device = f"DEV-UNKNOWN-{uuid.uuid4().hex[:6].upper()}"

    travel_start = detection_start + timedelta(days=3)

    for day_offset in range(3):
        current_day = travel_start + timedelta(days=day_offset)
        if current_day > detection_end:
            break

        # Unusual hour (02:00-04:00)
        login_dt = datetime(current_day.year, current_day.month, current_day.day,
                            rng.randint(2, 4), rng.randint(0, 59))
        session_id = str(uuid.uuid4())
        logins.append({
            "event_id": _make_event_id("LGN"),
            "timestamp": _ts(login_dt),
            "user_id": finance_user.user_id,
            "source_ip": travel_ip,
            "country": travel_country,
            "city": travel_city,
            "device_id": new_device,
            "auth_result": "success",
            "auth_method": "password",
            "session_id": session_id,
            "is_duplicate": False,
        })

        # Normal file access
        allowed_res = org.role_allowed_resources.get("Finance", [])
        for _ in range(rng.randint(5, 15)):
            if allowed_res:
                fa_dt = login_dt + timedelta(minutes=rng.randint(5, 60))
                files.append({
                    "event_id": _make_event_id("FAC"),
                    "timestamp": _ts(fa_dt),
                    "user_id": finance_user.user_id,
                    "session_id": session_id,
                    "resource_id": rng.choice(allowed_res),
                    "action": "read",
                    "result": "success",
                    "is_duplicate": False,
                })

    ground_truth.append({
        "scenario_id": "S8",
        "user_id": finance_user.user_id,
        "start_time": _ts(datetime.combine(travel_start, datetime.min.time())),
        "end_time": _ts(datetime.combine(min(travel_start + timedelta(days=2), detection_end),
                                         datetime.max.time().replace(microsecond=0))),
        "label": "TRUE_POSITIVE",
        "description": "Finance user logged in from new country (JP), unusual hours, new device — NO approved_travel context event to explain it.",
        "expected_min_score": 60,
        "expected_max_score": 100,
    })

    return {
        "login_events": logins,
        "file_access_events": files,
        "download_events": downloads,
        "privilege_events": privileges,
        "context_events": [],
        "ground_truth": ground_truth,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def inject_scenarios(
    org: OrgStructure,
    context_events: list,
    start_date: date,
    end_date: date,
    seed: int = 42,
) -> dict[str, list]:
    """
    Inject all 8 scenarios and return merged event dicts + ground_truth records.

    Returns dict with:
        login_events, file_access_events, download_events, privilege_events,
        context_events, ground_truth
    """
    rng = random.Random(seed + 999)

    all_logins: list[dict] = []
    all_files: list[dict] = []
    all_downloads: list[dict] = []
    all_privileges: list[dict] = []
    all_context: list[ContextEvent] = []
    all_ground_truth: list[dict] = []
    extra_users: list[dict] = []

    used_users: set[str] = set()

    def _merge(result: dict) -> None:
        if not result:
            return
        all_logins.extend(result.get("login_events", []))
        all_files.extend(result.get("file_access_events", []))
        all_downloads.extend(result.get("download_events", []))
        all_privileges.extend(result.get("privilege_events", []))
        all_context.extend(result.get("context_events", []))
        all_ground_truth.extend(result.get("ground_truth", []))
        extra_users.extend(result.get("extra_users", []))
        for gt in result.get("ground_truth", []):
            used_users.add(gt["user_id"])

    _merge(_scenario_s1(org, start_date, end_date, rng))
    _merge(_scenario_s2(org, start_date, end_date, rng))
    _merge(_scenario_s3(org, start_date, end_date, rng))
    _merge(_scenario_s4(org, start_date, end_date, rng, existing_user_ids=set(used_users)))
    _merge(_scenario_s5(org, start_date, end_date, rng))
    _merge(_scenario_s6(org, start_date, end_date, rng))
    _merge(_scenario_s7(org, start_date, end_date, rng))
    _merge(_scenario_s8(org, start_date, end_date, rng, existing_user_ids=set(used_users)))

    return {
        "login_events": all_logins,
        "file_access_events": all_files,
        "download_events": all_downloads,
        "privilege_events": all_privileges,
        "context_events": all_context,
        "ground_truth": all_ground_truth,
        "extra_users": extra_users,
    }
