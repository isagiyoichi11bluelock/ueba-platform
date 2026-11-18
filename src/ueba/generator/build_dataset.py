"""
build_dataset.py - Deterministic synthetic dataset generator & database loader.

Orchestrates org generation, normal baseline events, context events,
and scenario injection (S1-S8), then populates both data/*.csv and data/ueba.db.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from datetime import date, timedelta

from src.ueba.config import get_config
from src.ueba.db import get_connection, initialize_db, get_db_path
from src.ueba.privacy import get_pseudonym, pseudonymize_user_id, get_pseudonym_salt, truncate_ip
from src.ueba.audit import log_audit_event
from .org import generate_org
from .context import generate_context_events
from .normal import generate_normal_events
from .scenarios import inject_scenarios

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = PROJECT_ROOT / "data"


def build_dataset() -> None:
    """Generate all synthetic data, save CSVs, and load into SQLite."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg = get_config()
    end_date = cfg.get_end_date()
    start_date = cfg.get_start_date()
    
    logger.info(f"Generating synthetic dataset: {start_date} to {end_date} (seed={cfg.seed})")

    # 1. Organization & Resources
    org = generate_org(seed=cfg.seed, num_users=cfg.data.num_users, num_resources=cfg.data.num_resources)
    logger.info(f"Generated {len(org.users)} users ({sum(1 for u in org.users if u.is_contractor)} contractors), {len(org.resources)} resources")

    # 2. Context Events
    context_events = generate_context_events(org, start_date, end_date, seed=cfg.seed)
    logger.info(f"Generated {len(context_events)} context events (travel, month-end, on-call)")

    # 3. Normal Behavioral Events
    normal_events = generate_normal_events(org, context_events, start_date, end_date, seed=cfg.seed)

    # 4. Injected Threat & Benign Scenarios (S1–S8)
    scenario_data = inject_scenarios(org, context_events, start_date, end_date, seed=cfg.seed)
    ground_truth = scenario_data.get("ground_truth", [])
    logger.info(f"Injected {len(ground_truth)} ground-truth test scenarios (S1–S8)")

    # 5. Initialize Fresh Database
    db_path = get_db_path()
    if db_path.exists():
        try:
            db_path.unlink()
            logger.info("Removed existing database")
        except Exception:
            pass

    conn = get_connection()
    initialize_db(conn)
    salt = get_pseudonym_salt()

    # 6. Populate Users & Pseudonym Mapping
    user_rows = []
    for user in org.users:
        pseudonym = pseudonymize_user_id(user.user_id, salt)
        user_rows.append({
            "user_id": user.user_id,
            "pseudonym": pseudonym,
            "role": user.role,
            "department": user.department,
            "home_country": user.home_country,
            "home_city": user.home_city,
            "hire_date": user.hire_date.isoformat(),
            "work_start_hour": user.work_start_hour,
            "work_end_hour": user.work_end_hour,
            "timezone": user.timezone,
            "working_days": str(user.working_days),
            "is_manager": int(user.is_manager),
            "is_contractor": int(user.is_contractor),
            "is_night_shift": int(user.is_night_shift),
            "is_part_time": int(user.is_part_time),
        })
        conn.execute(
            """INSERT OR IGNORE INTO users 
               (user_id, pseudonym, role, department, home_country, home_city, 
                hire_date, work_start_hour, work_end_hour, timezone, working_days,
                is_manager, is_contractor, is_night_shift, is_part_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user.user_id, pseudonym, user.role, user.department, user.home_country,
             user.home_city, user.hire_date.isoformat(), user.work_start_hour, user.work_end_hour,
             user.timezone, str(user.working_days), int(user.is_manager), int(user.is_contractor),
             int(user.is_night_shift), int(user.is_part_time))
        )
        conn.execute(
            "INSERT OR IGNORE INTO pseudonym_map (user_id, pseudonym, created_at) VALUES (?, ?, datetime('now'))",
            (user.user_id, pseudonym)
        )
        for device_id in user.devices:
            conn.execute(
                "INSERT OR IGNORE INTO devices (device_id, user_id, device_type) VALUES (?, ?, ?)",
                (device_id, user.user_id, "managed_laptop")
            )

    # Insert extra users (e.g. S6 new joiner E0999)
    for eu in scenario_data.get("extra_users", []):
        eu_id = eu["user_id"]
        pseudonym = pseudonymize_user_id(eu_id, salt)
        user_rows.append({
            "user_id": eu_id,
            "pseudonym": pseudonym,
            "role": eu["role"],
            "department": eu["department"],
            "home_country": eu["home_country"],
            "home_city": eu["home_city"],
            "hire_date": eu["hire_date"],
            "work_start_hour": eu["work_start_hour"],
            "work_end_hour": eu["work_end_hour"],
            "timezone": eu["timezone"],
            "working_days": str(eu["working_days"]),
            "is_manager": int(eu.get("is_manager", 0)),
            "is_contractor": int(eu.get("is_contractor", 0)),
            "is_night_shift": int(eu.get("is_night_shift", 0)),
            "is_part_time": int(eu.get("is_part_time", 0)),
        })
        conn.execute(
            """INSERT OR IGNORE INTO users 
               (user_id, pseudonym, role, department, home_country, home_city, 
                hire_date, work_start_hour, work_end_hour, timezone, working_days,
                is_manager, is_contractor, is_night_shift, is_part_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eu_id, pseudonym, eu["role"], eu["department"], eu["home_country"],
             eu["home_city"], eu["hire_date"], eu["work_start_hour"], eu["work_end_hour"],
             eu["timezone"], str(eu["working_days"]), int(eu.get("is_manager", 0)),
             int(eu.get("is_contractor", 0)), int(eu.get("is_night_shift", 0)),
             int(eu.get("is_part_time", 0)))
        )
        conn.execute(
            "INSERT OR IGNORE INTO pseudonym_map (user_id, pseudonym, created_at) VALUES (?, ?, datetime('now'))",
            (eu_id, pseudonym)
        )
        for device_id in eu.get("devices", []):
            conn.execute(
                "INSERT OR IGNORE INTO devices (device_id, user_id, device_type) VALUES (?, ?, ?)",
                (device_id, eu_id, "managed_laptop")
            )

    # 7. Populate Resources & Permissions
    res_rows = []
    for res in org.resources:
        res_rows.append({
            "resource_id": res.resource_id,
            "resource_type": res.resource_type,
            "sensitivity": res.sensitivity,
            "owner_role": res.owner_role,
            "name": res.name,
        })
        conn.execute(
            "INSERT OR IGNORE INTO resources (resource_id, resource_type, sensitivity, owner_role, name) VALUES (?, ?, ?, ?, ?)",
            (res.resource_id, res.resource_type, res.sensitivity, res.owner_role, res.name)
        )

    for role, res_ids in org.role_allowed_resources.items():
        for res_id in res_ids:
            conn.execute("INSERT OR IGNORE INTO role_resource_access (role, resource_id, access_type) VALUES (?, ?, ?)", (role, res_id, "allowed"))
    for role, res_ids in org.role_typical_resources.items():
        for res_id in res_ids:
            conn.execute("INSERT OR REPLACE INTO role_resource_access (role, resource_id, access_type) VALUES (?, ?, ?)", (role, res_id, "typical"))

    conn.commit()

    # Combine events (deduplicate normal logins on days when scenario injected events exist for that user)
    scenario_logins = scenario_data.get("login_events", [])
    scenario_user_dates = {(ev["user_id"], ev["timestamp"][:10]) for ev in scenario_logins}
    filtered_normal_logins = [
        ev for ev in normal_events["login_events"]
        if (ev["user_id"], ev["timestamp"][:10]) not in scenario_user_dates
    ]

    all_logins = filtered_normal_logins + scenario_logins
    all_file_access = normal_events["file_access_events"] + scenario_data.get("file_access_events", [])
    all_downloads = normal_events["download_events"] + scenario_data.get("download_events", [])
    all_privileges = normal_events["privilege_events"] + scenario_data.get("privilege_events", [])

    # 8. Insert Activity Events (with IP truncation & pseudonymization)
    _insert_login_events(conn, all_logins, salt)
    _insert_file_access_events(conn, all_file_access, salt)
    _insert_download_events(conn, all_downloads, salt)
    _insert_privilege_events(conn, all_privileges, salt)

    # 9. Insert Context Events
    all_contexts = context_events + scenario_data.get("context_events", [])
    ctx_rows = []
    for ce in all_contexts:
        ctx_rows.append({
            "context_id": ce.context_id,
            "user_id": ce.user_id,
            "context_type": ce.context_type,
            "start_time": ce.start_time.isoformat(),
            "end_time": ce.end_time.isoformat(),
            "approved_by_role": ce.approved_by_role,
            "notes": ce.notes,
        })
        conn.execute(
            """INSERT OR IGNORE INTO context_events 
               (context_id, user_id, context_type, start_time, end_time, approved_by_role, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ce.context_id, ce.user_id, ce.context_type, 
             ce.start_time.isoformat(), ce.end_time.isoformat(),
             ce.approved_by_role, ce.notes)
        )

    # 10. Insert Ground Truth
    gt_rows = []
    for gt in ground_truth:
        gt_rows.append(gt)
        conn.execute(
            """INSERT OR REPLACE INTO ground_truth 
               (scenario_id, user_id, start_time, end_time, label, description, expected_min_score, expected_max_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (gt["scenario_id"], gt["user_id"], gt["start_time"], gt["end_time"],
             gt["label"], gt["description"], gt["expected_min_score"], gt["expected_max_score"])
        )

    conn.commit()

    # 11. Write CSV exports to data/
    pd.DataFrame(user_rows).to_csv(DATA_DIR / "users.csv", index=False)
    pd.DataFrame(res_rows).to_csv(DATA_DIR / "resources.csv", index=False)
    pd.DataFrame(all_logins).to_csv(DATA_DIR / "login_events.csv", index=False)
    pd.DataFrame(all_file_access).to_csv(DATA_DIR / "file_access_events.csv", index=False)
    pd.DataFrame(all_downloads).to_csv(DATA_DIR / "download_events.csv", index=False)
    pd.DataFrame(all_privileges).to_csv(DATA_DIR / "privilege_events.csv", index=False)
    pd.DataFrame(ctx_rows).to_csv(DATA_DIR / "context_events.csv", index=False)
    pd.DataFrame(gt_rows).to_csv(DATA_DIR / "ground_truth.csv", index=False)

    # 12. Audit event
    log_audit_event(conn, actor="system", action="DATA_GENERATION", details={
        "users": len(org.users),
        "resources": len(org.resources),
        "login_events": len(all_logins),
        "file_access_events": len(all_file_access),
        "download_events": len(all_downloads),
        "privilege_events": len(all_privileges),
        "scenarios": len(ground_truth),
    })

    conn.close()
    logger.info("Dataset generation & database ingestion complete!")
    logger.info(f"  • Logins: {len(all_logins)}")
    logger.info(f"  • File Access: {len(all_file_access)}")
    logger.info(f"  • Downloads: {len(all_downloads)}")
    logger.info(f"  • Privilege Invocations: {len(all_privileges)}")


def _insert_login_events(conn, events: list[dict], salt: str) -> None:
    for ev in events:
        pseudonym = pseudonymize_user_id(ev["user_id"], salt)
        ip = ev.get("source_ip", "10.0.0.1")
        ip_truncated = truncate_ip(ip)
        conn.execute(
            """INSERT OR IGNORE INTO login_events 
               (event_id, timestamp, user_id, pseudonym_id, source_ip, source_ip_truncated,
                country, city, device_id, auth_result, auth_method, session_id, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ev["event_id"], ev["timestamp"], ev["user_id"], pseudonym,
             ip, ip_truncated,
             ev.get("country", "US"), ev.get("city", "New York"),
             ev.get("device_id", "DEV-1"), ev.get("auth_result", "success"),
             ev.get("auth_method", "password"), ev.get("session_id", ""),
             int(ev.get("is_duplicate", False)))
        )


def _insert_file_access_events(conn, events: list[dict], salt: str) -> None:
    for ev in events:
        pseudonym = pseudonymize_user_id(ev["user_id"], salt)
        conn.execute(
            """INSERT OR IGNORE INTO file_access_events
               (event_id, timestamp, user_id, pseudonym_id, session_id, resource_id, action, result, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ev["event_id"], ev["timestamp"], ev["user_id"], pseudonym,
             ev.get("session_id", ""), ev.get("resource_id", ""),
             ev.get("action", "read"), ev.get("result", "success"),
             int(ev.get("is_duplicate", False)))
        )


def _insert_download_events(conn, events: list[dict], salt: str) -> None:
    for ev in events:
        pseudonym = pseudonymize_user_id(ev["user_id"], salt)
        conn.execute(
            """INSERT OR IGNORE INTO download_events
               (event_id, timestamp, user_id, pseudonym_id, session_id, resource_id, bytes, file_count, destination_type, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ev["event_id"], ev["timestamp"], ev["user_id"], pseudonym,
             ev.get("session_id", ""), ev.get("resource_id", ""),
             ev.get("bytes", 0), ev.get("file_count", 1),
             ev.get("destination_type", "managed_laptop"),
             int(ev.get("is_duplicate", False)))
        )


def _insert_privilege_events(conn, events: list[dict], salt: str) -> None:
    for ev in events:
        pseudonym = pseudonymize_user_id(ev["user_id"], salt)
        conn.execute(
            """INSERT OR IGNORE INTO privilege_events
               (event_id, timestamp, user_id, pseudonym_id, session_id, action, target, result, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ev["event_id"], ev["timestamp"], ev["user_id"], pseudonym,
             ev.get("session_id", ""), ev.get("action", ""),
             ev.get("target", ""), ev.get("result", "success"),
             int(ev.get("is_duplicate", False)))
        )


if __name__ == "__main__":
    build_dataset()
