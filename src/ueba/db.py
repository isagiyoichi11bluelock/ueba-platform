"""SQLite schema creation and helper functions for the UEBA platform."""
from __future__ import annotations
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_db_path() -> Path:
    """Return path to the SQLite database file."""
    return PROJECT_ROOT / "data" / "ueba.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set to sqlite3.Row."""
    if db_path is None:
        db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_db(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist."""
    conn.executescript("""
        -- Users
        CREATE TABLE IF NOT EXISTS users (
            user_id          TEXT PRIMARY KEY,
            pseudonym        TEXT,
            role             TEXT,
            department       TEXT,
            home_country     TEXT,
            home_city        TEXT,
            hire_date        TEXT,
            work_start_hour  INTEGER,
            work_end_hour    INTEGER,
            timezone         TEXT,
            working_days     TEXT,
            is_manager       INTEGER,
            is_contractor    INTEGER,
            is_night_shift   INTEGER,
            is_part_time     INTEGER
        );

        -- Devices
        CREATE TABLE IF NOT EXISTS devices (
            device_id    TEXT PRIMARY KEY,
            user_id      TEXT,
            device_type  TEXT
        );

        -- Resources
        CREATE TABLE IF NOT EXISTS resources (
            resource_id    TEXT PRIMARY KEY,
            resource_type  TEXT,
            sensitivity    TEXT,
            owner_role     TEXT,
            name           TEXT
        );

        -- Role-resource access (allowed and typical)
        CREATE TABLE IF NOT EXISTS role_resource_access (
            role         TEXT,
            resource_id  TEXT,
            access_type  TEXT
        );

        -- Login events
        CREATE TABLE IF NOT EXISTS login_events (
            event_id             TEXT PRIMARY KEY,
            timestamp            TEXT,
            user_id              TEXT,
            pseudonym_id         TEXT,
            source_ip            TEXT,
            source_ip_truncated  TEXT,
            country              TEXT,
            city                 TEXT,
            device_id            TEXT,
            auth_result          TEXT,
            auth_method          TEXT,
            session_id           TEXT,
            is_duplicate         INTEGER DEFAULT 0
        );

        -- File access events
        CREATE TABLE IF NOT EXISTS file_access_events (
            event_id      TEXT PRIMARY KEY,
            timestamp     TEXT,
            user_id       TEXT,
            pseudonym_id  TEXT,
            session_id    TEXT,
            resource_id   TEXT,
            action        TEXT,
            result        TEXT,
            is_duplicate  INTEGER DEFAULT 0
        );

        -- Download events
        CREATE TABLE IF NOT EXISTS download_events (
            event_id          TEXT PRIMARY KEY,
            timestamp         TEXT,
            user_id           TEXT,
            pseudonym_id      TEXT,
            session_id        TEXT,
            resource_id       TEXT,
            bytes             INTEGER,
            file_count        INTEGER,
            destination_type  TEXT,
            is_duplicate      INTEGER DEFAULT 0
        );

        -- Privilege events
        CREATE TABLE IF NOT EXISTS privilege_events (
            event_id      TEXT PRIMARY KEY,
            timestamp     TEXT,
            user_id       TEXT,
            pseudonym_id  TEXT,
            session_id    TEXT,
            action        TEXT,
            target        TEXT,
            result        TEXT,
            is_duplicate  INTEGER DEFAULT 0
        );

        -- Context events (approved travel, on-call, etc.)
        CREATE TABLE IF NOT EXISTS context_events (
            context_id        TEXT PRIMARY KEY,
            user_id           TEXT,
            context_type      TEXT,
            start_time        TEXT,
            end_time          TEXT,
            approved_by_role  TEXT,
            notes             TEXT
        );

        -- Ground truth (injected scenarios for evaluation)
        CREATE TABLE IF NOT EXISTS ground_truth (
            scenario_id         TEXT PRIMARY KEY,
            user_id             TEXT,
            start_time          TEXT,
            end_time            TEXT,
            label               TEXT,
            description         TEXT,
            expected_min_score  REAL,
            expected_max_score  REAL
        );

        -- User baselines
        CREATE TABLE IF NOT EXISTS user_baselines (
            baseline_id    TEXT PRIMARY KEY,
            user_id        TEXT,
            computed_date  TEXT,
            baseline_type  TEXT,
            metric_name    TEXT,
            metric_value   TEXT,
            confidence     REAL
        );

        -- Role baselines
        CREATE TABLE IF NOT EXISTS role_baselines (
            baseline_id    TEXT PRIMARY KEY,
            role           TEXT,
            computed_date  TEXT,
            metric_name    TEXT,
            metric_value   TEXT
        );

        -- Alerts
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id               TEXT PRIMARY KEY,
            user_id                TEXT,
            pseudonym_id           TEXT,
            alert_date             TEXT,
            risk_score             REAL,
            severity_band          TEXT,
            indicators_json        TEXT,
            context_applied_json   TEXT,
            summary                TEXT,
            baseline_confidence    REAL,
            status                 TEXT DEFAULT 'open',
            scenario_id            TEXT
        );

        -- Tamper-evident audit log
        CREATE TABLE IF NOT EXISTS audit_log (
            entry_id      TEXT PRIMARY KEY,
            timestamp     TEXT,
            actor         TEXT,
            action        TEXT,
            details_json  TEXT,
            prev_hash     TEXT,
            entry_hash    TEXT
        );

        -- Analyst feedback
        CREATE TABLE IF NOT EXISTS analyst_feedback (
            feedback_id  TEXT PRIMARY KEY,
            alert_id     TEXT,
            analyst      TEXT,
            verdict      TEXT,
            comment      TEXT,
            created_at   TEXT
        );

        -- Adjustment rules (per-user, per-indicator score dampening)
        CREATE TABLE IF NOT EXISTS adjustment_rules (
            rule_id            TEXT PRIMARY KEY,
            user_id            TEXT,
            indicator_id       TEXT,
            adjustment_factor  REAL,
            reason             TEXT,
            created_by         TEXT,
            created_at         TEXT,
            expires_at         TEXT,
            is_active          INTEGER DEFAULT 1
        );

        -- Pseudonym map (SEPARATE – not read by dashboard normally)
        CREATE TABLE IF NOT EXISTS pseudonym_map (
            user_id     TEXT PRIMARY KEY,
            pseudonym   TEXT,
            created_at  TEXT
        );

        -- Identity map access log (gated re-identification audit trail)
        CREATE TABLE IF NOT EXISTS identity_map_access_log (
            access_id      TEXT PRIMARY KEY,
            pseudonym      TEXT,
            accessed_by    TEXT,
            justification  TEXT,
            timestamp      TEXT,
            audit_entry_id TEXT
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_login_user   ON login_events (user_id);
        CREATE INDEX IF NOT EXISTS idx_login_ts     ON login_events (timestamp);
        CREATE INDEX IF NOT EXISTS idx_login_dup    ON login_events (is_duplicate);

        CREATE INDEX IF NOT EXISTS idx_file_user    ON file_access_events (user_id);
        CREATE INDEX IF NOT EXISTS idx_file_ts      ON file_access_events (timestamp);

        CREATE INDEX IF NOT EXISTS idx_dl_user      ON download_events (user_id);
        CREATE INDEX IF NOT EXISTS idx_dl_ts        ON download_events (timestamp);

        CREATE INDEX IF NOT EXISTS idx_priv_user    ON privilege_events (user_id);
        CREATE INDEX IF NOT EXISTS idx_priv_ts      ON privilege_events (timestamp);

        CREATE INDEX IF NOT EXISTS idx_ctx_user     ON context_events (user_id);
        CREATE INDEX IF NOT EXISTS idx_ctx_type     ON context_events (context_type);

        CREATE INDEX IF NOT EXISTS idx_alerts_user  ON alerts (user_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_date  ON alerts (alert_date);
        CREATE INDEX IF NOT EXISTS idx_alerts_sev   ON alerts (severity_band);
        CREATE INDEX IF NOT EXISTS idx_alerts_st    ON alerts (status);

        CREATE INDEX IF NOT EXISTS idx_bl_user      ON user_baselines (user_id);
        CREATE INDEX IF NOT EXISTS idx_bl_date      ON user_baselines (computed_date);

        CREATE INDEX IF NOT EXISTS idx_audit_ts     ON audit_log (timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_log (actor);

        CREATE INDEX IF NOT EXISTS idx_adj_user     ON adjustment_rules (user_id);
        CREATE INDEX IF NOT EXISTS idx_adj_active   ON adjustment_rules (is_active);

        CREATE INDEX IF NOT EXISTS idx_pmap_pseudo  ON pseudonym_map (pseudonym);
        CREATE INDEX IF NOT EXISTS idx_idmap_pseudo ON identity_map_access_log (pseudonym);

        CREATE INDEX IF NOT EXISTS idx_fb_alert     ON analyst_feedback (alert_id);
        CREATE INDEX IF NOT EXISTS idx_fb_analyst   ON analyst_feedback (analyst);

        CREATE INDEX IF NOT EXISTS idx_rra_role     ON role_resource_access (role);
        CREATE INDEX IF NOT EXISTS idx_rra_res      ON role_resource_access (resource_id);

        CREATE INDEX IF NOT EXISTS idx_gt_user      ON ground_truth (user_id);
        CREATE INDEX IF NOT EXISTS idx_dev_user     ON devices (user_id);
    """)
    conn.commit()


def close_db(conn: sqlite3.Connection) -> None:
    """Close a database connection."""
    conn.close()
