"""CSV/JSON -> validated -> SQLite loader with duplicate detection and repair."""
from __future__ import annotations

import csv
import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic validation models
# ---------------------------------------------------------------------------

class LoginEventRow(BaseModel):
    event_id:            str
    timestamp:           str
    user_id:             str
    pseudonym_id:        str = ""
    source_ip:           str = ""
    source_ip_truncated: str = ""
    country:             str = ""
    city:                str = ""
    device_id:           str = ""
    auth_result:         str = ""
    auth_method:         str = ""
    session_id:          str = ""
    is_duplicate:        int = 0

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid timestamp: {v}")
        return v

    @field_validator("is_duplicate", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> int:
        if isinstance(v, str):
            return 1 if v.lower() in ("1", "true", "yes") else 0
        return int(v)


class FileAccessEventRow(BaseModel):
    event_id:     str
    timestamp:    str
    user_id:      str
    pseudonym_id: str = ""
    session_id:   str = ""
    resource_id:  str = ""
    action:       str = ""
    result:       str = ""
    is_duplicate: int = 0

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v

    @field_validator("is_duplicate", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> int:
        if isinstance(v, str):
            return 1 if v.lower() in ("1", "true", "yes") else 0
        return int(v)


class DownloadEventRow(BaseModel):
    event_id:         str
    timestamp:        str
    user_id:          str
    pseudonym_id:     str = ""
    session_id:       str = ""
    resource_id:      str = ""
    bytes:            int = 0
    file_count:       int = 0
    destination_type: str = ""
    is_duplicate:     int = 0

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v

    @field_validator("bytes", "file_count", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @field_validator("is_duplicate", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> int:
        if isinstance(v, str):
            return 1 if v.lower() in ("1", "true", "yes") else 0
        return int(v)


class PrivilegeEventRow(BaseModel):
    event_id:     str
    timestamp:    str
    user_id:      str
    pseudonym_id: str = ""
    session_id:   str = ""
    action:       str = ""
    target:       str = ""
    result:       str = ""
    is_duplicate: int = 0

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v

    @field_validator("is_duplicate", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> int:
        if isinstance(v, str):
            return 1 if v.lower() in ("1", "true", "yes") else 0
        return int(v)


class ContextEventRow(BaseModel):
    context_id:       str
    user_id:          str
    context_type:     str
    start_time:       str
    end_time:         str = ""
    approved_by_role: str = ""
    notes:            str = ""


class GroundTruthRow(BaseModel):
    scenario_id:        str
    user_id:            str
    start_time:         str
    end_time:           str
    label:              str
    description:        str = ""
    expected_min_score: float = 0.0
    expected_max_score: float = 100.0

    @field_validator("expected_min_score", "expected_max_score", mode="before")
    @classmethod
    def coerce_float(cls, v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0


# ---------------------------------------------------------------------------
# Table -> (model, insert SQL, columns)
# ---------------------------------------------------------------------------

_TABLE_CONFIG: dict[str, dict] = {
    "login_events": {
        "model": LoginEventRow,
        "columns": [
            "event_id", "timestamp", "user_id", "pseudonym_id",
            "source_ip", "source_ip_truncated", "country", "city",
            "device_id", "auth_result", "auth_method", "session_id", "is_duplicate",
        ],
        "pk": "event_id",
    },
    "file_access_events": {
        "model": FileAccessEventRow,
        "columns": [
            "event_id", "timestamp", "user_id", "pseudonym_id",
            "session_id", "resource_id", "action", "result", "is_duplicate",
        ],
        "pk": "event_id",
    },
    "download_events": {
        "model": DownloadEventRow,
        "columns": [
            "event_id", "timestamp", "user_id", "pseudonym_id",
            "session_id", "resource_id", "bytes", "file_count",
            "destination_type", "is_duplicate",
        ],
        "pk": "event_id",
    },
    "privilege_events": {
        "model": PrivilegeEventRow,
        "columns": [
            "event_id", "timestamp", "user_id", "pseudonym_id",
            "session_id", "action", "target", "result", "is_duplicate",
        ],
        "pk": "event_id",
    },
    "context_events": {
        "model": ContextEventRow,
        "columns": [
            "context_id", "user_id", "context_type", "start_time",
            "end_time", "approved_by_role", "notes",
        ],
        "pk": "context_id",
    },
    "ground_truth": {
        "model": GroundTruthRow,
        "columns": [
            "scenario_id", "user_id", "start_time", "end_time",
            "label", "description", "expected_min_score", "expected_max_score",
        ],
        "pk": "scenario_id",
    },
}


# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------

def _read_rows(file_path: Path) -> list[dict[str, Any]]:
    """Read rows from CSV or JSON file."""
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        with open(file_path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    elif suffix == ".json":
        with open(file_path, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else [data]
    elif suffix == ".jsonl":
        rows = []
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def _auto_pk(table_name: str) -> str:
    """Generate a UUID primary key for a row that is missing one."""
    return str(uuid.uuid4())


def load_events_from_csv(
    table_name: str,
    csv_path: Path,
    conn: sqlite3.Connection,
    batch_size: int = 500,
) -> dict[str, int]:
    """
    Load events from a CSV/JSON/JSONL file into the given table.

    Handles:
    - ~0.5% duplicates: detected via INSERT OR IGNORE on PK; counted separately.
    - ~0.3% missing optional fields: Pydantic fills defaults; logged as repaired.
    - Validation failures: row is rejected and logged; processing continues.

    Returns a summary dict:
      {
        "loaded":   int,   # successfully inserted
        "rejected": int,   # failed pydantic validation
        "repaired": int,   # inserted with default-filled fields
        "skipped":  int,   # duplicate PKs (already in DB)
      }
    """
    if table_name not in _TABLE_CONFIG:
        raise ValueError(
            f"Unknown table '{table_name}'. Known tables: {list(_TABLE_CONFIG.keys())}"
        )

    cfg = _TABLE_CONFIG[table_name]
    Model = cfg["model"]
    columns = cfg["columns"]
    pk_col = cfg["pk"]

    placeholders = ", ".join("?" for _ in columns)
    col_list = ", ".join(columns)
    insert_sql = (
        f"INSERT OR IGNORE INTO {table_name} ({col_list}) VALUES ({placeholders})"
    )

    raw_rows = _read_rows(csv_path)
    stats = {"loaded": 0, "rejected": 0, "repaired": 0, "skipped": 0}

    batch: list[tuple] = []

    def _flush(batch: list[tuple]) -> None:
        if not batch:
            return
        conn.executemany(insert_sql, batch)
        conn.commit()

    for line_no, raw in enumerate(raw_rows, start=1):
        # Ensure PK exists (auto-generate if missing)
        if pk_col not in raw or not raw[pk_col]:
            raw[pk_col] = _auto_pk(table_name)
            logger.debug("Row %d: auto-generated %s=%s", line_no, pk_col, raw[pk_col])

        # Track whether any field was repaired (defaulted)
        original_keys = set(raw.keys())

        try:
            obj = Model(**raw)
        except ValidationError as exc:
            logger.warning(
                "Row %d rejected from %s: %s | raw=%s",
                line_no,
                table_name,
                exc.errors(),
                raw,
            )
            stats["rejected"] += 1
            continue

        obj_dict = obj.model_dump()
        repaired = any(
            col not in original_keys or (original_keys and raw.get(col) in (None, ""))
            for col in columns
            if col != pk_col
        )
        if repaired:
            stats["repaired"] += 1
            logger.debug("Row %d repaired (defaults applied): pk=%s", line_no, obj_dict[pk_col])

        values = tuple(obj_dict[col] for col in columns)
        batch.append(values)

        if len(batch) >= batch_size:
            before = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            _flush(batch)
            after = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            inserted = after - before
            skipped = len(batch) - inserted
            stats["loaded"] += inserted
            stats["skipped"] += skipped
            batch = []

    # Flush remainder
    if batch:
        before = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        _flush(batch)
        after = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        inserted = after - before
        skipped = len(batch) - inserted
        stats["loaded"] += inserted
        stats["skipped"] += skipped

    logger.info(
        "load_events_from_csv(%s, %s): %s",
        table_name,
        csv_path.name,
        stats,
    )
    return stats


def load_events_from_records(
    table_name: str,
    records: list[dict[str, Any]],
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """
    Convenience wrapper to load from an in-memory list of dicts
    (used by the data generator to avoid a CSV round-trip).
    """
    import tempfile
    import os

    # Write to a temp CSV and delegate
    if not records:
        return {"loaded": 0, "rejected": 0, "repaired": 0, "skipped": 0}

    cfg = _TABLE_CONFIG[table_name]
    columns = cfg["columns"]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
        tmp_path = Path(tmp.name)

    try:
        return load_events_from_csv(table_name, tmp_path, conn)
    finally:
        os.unlink(tmp_path)
