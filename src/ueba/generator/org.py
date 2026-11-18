"""Organization structure: users, roles, resources, devices."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

# RFC 5737 test ranges and private ranges for IPs
PRIVATE_IP_PREFIXES = [
    "10.0.", "10.1.", "172.16.", "192.168.1.", "192.168.2.",
    "198.51.100.", "203.0.113."
]

# City coordinates (lat, lon) for impossible travel detection
CITY_COORDS: dict[str, tuple[float, float]] = {
    "New York": (40.71, -74.01),
    "London": (51.51, -0.13),
    "Tokyo": (35.69, 139.69),
    "Sydney": (-33.87, 151.21),
    "Paris": (48.85, 2.35),
    "Berlin": (52.52, 13.41),
    "Mumbai": (19.08, 72.88),
    "Singapore": (1.35, 103.82),
    "Dubai": (25.20, 55.27),
    "Toronto": (43.65, -79.38),
    "Chicago": (41.88, -87.63),
    "São Paulo": (-23.55, -46.63),
    "Amsterdam": (52.37, 4.90),
    "Seoul": (37.57, 126.98),
    "Mexico City": (19.43, -99.13),
    "Cairo": (30.06, 31.25),
    "Lagos": (6.52, 3.38),
    "Nairobi": (-1.29, 36.82),
    "Bangalore": (12.97, 77.59),
    "Shanghai": (31.23, 121.47),
}

COUNTRIES_BY_CITY = {
    "New York": "US", "Chicago": "US", "Toronto": "CA",
    "London": "GB", "Paris": "FR", "Berlin": "DE", "Amsterdam": "NL",
    "Tokyo": "JP", "Seoul": "KR", "Shanghai": "CN", "Singapore": "SG",
    "Mumbai": "IN", "Bangalore": "IN",
    "Sydney": "AU",
    "Dubai": "AE",
    "São Paulo": "BR", "Mexico City": "MX",
    "Cairo": "EG", "Lagos": "NG", "Nairobi": "KE",
}


@dataclass
class User:
    user_id: str
    role: str
    department: str
    home_country: str
    home_city: str
    devices: list[str]
    hire_date: date
    work_start_hour: int
    work_end_hour: int
    timezone: str
    working_days: list[int]  # 0=Mon...6=Sun
    is_manager: bool
    is_contractor: bool
    is_night_shift: bool
    is_part_time: bool


@dataclass
class Resource:
    resource_id: str
    resource_type: str
    sensitivity: str  # Public, Internal, Confidential, Restricted
    owner_role: str
    name: str


@dataclass
class OrgStructure:
    users: list[User]
    resources: list[Resource]
    role_allowed_resources: dict[str, list[str]]
    role_typical_resources: dict[str, list[str]]


ROLES = {
    "Developer": {"count": 15, "department": "Engineering"},
    "Finance": {"count": 10, "department": "Finance"},
    "HR": {"count": 6, "department": "HR"},
    "Sales": {"count": 12, "department": "Sales"},
    "IT Admin": {"count": 7, "department": "IT"},
    "Contractor": {"count": 10, "department": "Various"},
}

RESOURCE_TYPES_BY_ROLE = {
    "Developer": ["code_repo", "ci_cd", "staging_db", "internal_wiki"],
    "Finance": ["finance_ledger", "hr_records", "reporting_db", "internal_wiki"],
    "HR": ["hr_records", "payroll_db", "internal_wiki"],
    "Sales": ["crm_db", "marketing_assets", "reporting_db", "internal_wiki"],
    "IT Admin": ["admin_console", "network_config", "all_dbs", "internal_wiki"],
    "Contractor": ["code_repo", "staging_db", "internal_wiki"],
}


def generate_org(
    seed: int = 42,
    num_users: int = 60,
    num_resources: int = 150,
    num_contractors: int = 10,
    **kwargs,
) -> OrgStructure:
    """Generate deterministic org structure."""
    rng = random.Random(seed)

    users = []
    user_counter = 1

    home_cities = list(CITY_COORDS.keys())
    timezones = ["UTC", "US/Eastern", "US/Pacific", "Europe/London", "Asia/Tokyo", "Asia/Kolkata"]

    # Night shift users (3) and part-time (2)
    night_shift_slots = set(rng.sample(range(60), 3))
    part_time_slots = set(rng.sample([x for x in range(60) if x not in night_shift_slots], 2))

    idx = 0
    for role, info in ROLES.items():
        is_contractor = (role == "Contractor")
        for i in range(info["count"]):
            uid = f"E{user_counter:04d}"
            city = rng.choice(home_cities)
            country = COUNTRIES_BY_CITY[city]
            is_night = idx in night_shift_slots
            is_part = idx in part_time_slots

            if is_night:
                start_h, end_h = 22, 6
            elif is_part:
                start_h = rng.choice([8, 9, 10])
                end_h = start_h + 4
            else:
                start_h = rng.randint(7, 10)
                end_h = start_h + rng.randint(7, 9)

            # Working days (part-time: 3 days, normal: 5 days Mon-Fri)
            if is_part:
                working_days = rng.sample([0, 1, 2, 3, 4], 3)
            else:
                working_days = [0, 1, 2, 3, 4]

            # Assign 1-2 devices
            num_devices = rng.choice([1, 1, 2])
            devices = [f"DEV-{uid}-{j+1}" for j in range(num_devices)]

            hire_date = date(2022, 1, 1) + timedelta(days=rng.randint(0, 1000))
            is_manager = (i == 0 and not is_contractor)

            users.append(User(
                user_id=uid,
                role=role,
                department=info["department"],
                home_country=country,
                home_city=city,
                devices=devices,
                hire_date=hire_date,
                work_start_hour=start_h,
                work_end_hour=end_h,
                timezone=rng.choice(timezones),
                working_days=sorted(working_days),
                is_manager=is_manager,
                is_contractor=is_contractor,
                is_night_shift=is_night,
                is_part_time=is_part,
            ))
            user_counter += 1
            idx += 1

    # Generate resources
    resources = []
    role_allowed: dict[str, list[str]] = {r: [] for r in ROLES}
    role_typical: dict[str, list[str]] = {r: [] for r in ROLES}

    sensitivity_levels = ["Public", "Internal", "Confidential", "Restricted"]
    sensitivity_weights = [0.3, 0.4, 0.2, 0.1]

    res_types = {
        "code_repo": "Developer",
        "finance_ledger": "Finance",
        "hr_records": "HR",
        "crm_db": "Sales",
        "admin_console": "IT Admin",
        "staging_db": "Developer",
        "payroll_db": "HR",
        "marketing_assets": "Sales",
        "reporting_db": "Finance",
        "internal_wiki": None,
        "network_config": "IT Admin",
        "ci_cd": "Developer",
        "all_dbs": "IT Admin",
    }

    for i in range(num_resources):
        res_id = f"RES-{i+1:04d}"
        rtype = rng.choice(list(res_types.keys()))
        sensitivity = rng.choices(sensitivity_levels, weights=sensitivity_weights)[0]
        owner_role = res_types[rtype] or "IT Admin"

        resources.append(Resource(
            resource_id=res_id,
            resource_type=rtype,
            sensitivity=sensitivity,
            owner_role=owner_role,
            name=f"{rtype.replace('_', ' ').title()} {i+1}",
        ))

    # Assign allowed and typical resources per role
    for resource in resources:
        for role in ROLES:
            allowed_types = RESOURCE_TYPES_BY_ROLE.get(role, [])
            if resource.resource_type in allowed_types or resource.sensitivity == "Public":
                role_allowed[role].append(resource.resource_id)
            # Typical = subset of allowed (most accessed)
            if resource.resource_type in allowed_types[:2]:
                role_typical[role].append(resource.resource_id)

    return OrgStructure(
        users=users,
        resources=resources,
        role_allowed_resources=role_allowed,
        role_typical_resources=role_typical,
    )
