# UEBA Platform — Data Dictionary

This document details the schema, column definitions, data types, constraints, and privacy transformations for all relational tables within the platform's SQLite database (`data/ueba.db`).

---

## 1. Organization & Identity Tables

### `users`
Core employee profile table. In analytics mode, this table is pseudonymized.

| Column | Type | Nullable | Description | Privacy / Security Treatment |
|---|---|---|---|---|
| `user_id` | TEXT | NO (PK) | Internal employee identifier (e.g., `E0001`) | Masked in analytics views; isolated from untrusted roles |
| `pseudonym` | TEXT | NO | HMAC-SHA256 token (e.g., `U-A1B2C3`) | Primary display token in dashboard |
| `role` | TEXT | NO | Functional job title (Developer, Finance, HR, Sales, IT Admin, Contractor) | Role classification used for peer group baselines |
| `department` | TEXT | NO | Departmental division (Engineering, Finance, HR, Sales, IT, Various) | Analytical grouping |
| `home_country` | TEXT | NO | 2-letter ISO country code of permanent residence | Regional baseline anchor |
| `home_city` | TEXT | NO | Primary base city | Geolocation baseline anchor |
| `hire_date` | TEXT | NO | ISO 8601 date of employment start | Used to calculate tenure and cold-start flags |
| `work_start_hour`| INTEGER | NO | Typical shift start hour (0–23 local time) | Establishes working hour expectations |
| `work_end_hour` | INTEGER | NO | Typical shift end hour (0–23 local time) | Supports night-shift and part-time workers |
| `timezone` | TEXT | NO | Standard Olson timezone string (e.g., `US/Eastern`) | Normalizes event timestamps to local clock |
| `working_days` | TEXT | NO | JSON array of active weekdays (0=Mon, 6=Sun) | Supports 3-day part-time schedules |
| `is_manager` | INTEGER | NO | Boolean flag (1=True, 0=False) | Permission hierarchy classification |
| `is_contractor` | INTEGER | NO | Boolean flag (1=True, 0=False) | Elevated sensitivity monitoring flag |
| `is_night_shift`| INTEGER | NO | Boolean flag (1=True, 0=False) | Prevents false positives on night activity |
| `is_part_time` | INTEGER | NO | Boolean flag (1=True, 0=False) | Prevents false positives on intermittent days |

---

### `pseudonym_map` (Restricted Separation-of-Duties Table)
Isolated table mapping raw employee IDs to pseudonyms. Governed by gated re-identification protocol.

| Column | Type | Nullable | Description | Privacy / Security Treatment |
|---|---|---|---|---|
| `user_id` | TEXT | NO (PK) | Cleartext internal employee ID | Strictly segregated; inaccessible by standard dashboard queries |
| `pseudonym` | TEXT | NO (Unique) | Pseudonymous token | Public reference token |
| `created_at` | TEXT | NO | ISO 8601 UTC creation timestamp | Audit trail |

---

### `identity_map_access_log`
Audit table recording all gated re-identification events.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `access_id` | TEXT | NO (PK) | UUID4 access record ID |
| `pseudonym` | TEXT | NO | Requested pseudonym token |
| `accessed_by` | TEXT | NO | Username of requester (must be `senior_analyst`) |
| `justification` | TEXT | NO | Formal business justification (minimum 20 characters) |
| `timestamp` | TEXT | NO | ISO 8601 UTC timestamp of access |
| `audit_entry_id` | TEXT | NO (FK) | Reference to immutable cryptographic audit log |

---

## 2. Event Activity Tables

### `login_events`
Authentication and session initialization records.

| Column | Type | Nullable | Description | Privacy Treatment |
|---|---|---|---|---|
| `event_id` | TEXT | NO (PK) | Unique event identifier (`L-xxxxxxxx`) | Synthetic ID |
| `timestamp` | TEXT | NO | ISO 8601 UTC timestamp | Preserved for timeline and velocity analysis |
| `user_id` | TEXT | NO | Raw user ID (stripped in minimized analytics exports) | Retained internally |
| `pseudonym_id` | TEXT | NO | HMAC pseudonym token | Primary joining key |
| `source_ip` | TEXT | NO | RFC 5737 synthetic source IPv4 address | Never exported to dashboard |
| `source_ip_truncated`| TEXT | NO | IPv4 /24 subnet (e.g., `198.51.100.0/24`) | Data minimization compliance |
| `country` | TEXT | NO | Country code inferred from IP | Granular to country level only |
| `city` | TEXT | NO | City inferred from IP | Used for speed/distance calculation |
| `device_id` | TEXT | NO | Unique hardware asset tag | Tagged as managed/unrecognized |
| `auth_result` | TEXT | NO | `success` or `failure` | Burst detection trigger |
| `auth_method` | TEXT | NO | `password`, `mfa`, or `sso` | Multi-factor correlation |
| `session_id` | TEXT | NO | UUID4 session tracking token | Correlates downstream file activity |
| `is_duplicate` | INTEGER | NO | Ingest deduplication flag | Retained for data pipeline quality audits |

---

### `file_access_events`
Resource interaction records (read, write, delete, share).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `event_id` | TEXT | NO (PK) | Unique file access ID (`FA-xxxxxxxx`) |
| `timestamp` | TEXT | NO | ISO 8601 UTC timestamp |
| `user_id` | TEXT | NO | Employee identifier |
| `pseudonym_id` | TEXT | NO | Pseudonym token |
| `session_id` | TEXT | NO | Originating login session reference |
| `resource_id` | TEXT | NO (FK) | Target resource identifier (`RES-xxxx`) |
| `action` | TEXT | NO | File operation: `read`, `write`, `delete`, `share` |
| `result` | TEXT | NO | `success` or `denied` |
| `is_duplicate` | INTEGER | NO | Data quality flag |

---

### `download_events`
Data egress and file download records.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `event_id` | TEXT | NO (PK) | Unique download event ID (`DL-xxxxxxxx`) |
| `timestamp` | TEXT | NO | ISO 8601 UTC timestamp |
| `user_id` | TEXT | NO | Employee identifier |
| `pseudonym_id` | TEXT | NO | Pseudonym token |
| `session_id` | TEXT | NO | Originating session ID |
| `resource_id` | TEXT | NO | Resource downloaded |
| `bytes` | INTEGER | NO | Transfer volume in bytes |
| `file_count` | INTEGER | NO | Number of files bundled |
| `destination_type`| TEXT | NO | `managed_laptop`, `personal_device`, `external_share` |
| `is_duplicate` | INTEGER | NO | Ingest quality flag |

---

### `privilege_events`
Administrative, sudo, and IAM operations.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `event_id` | TEXT | NO (PK) | Unique privilege operation ID (`PR-xxxxxxxx`) |
| `timestamp` | TEXT | NO | ISO 8601 UTC timestamp |
| `user_id` | TEXT | NO | Employee identifier |
| `pseudonym_id` | TEXT | NO | Pseudonym token |
| `session_id` | TEXT | NO | Originating session ID |
| `action` | TEXT | NO | `role_grant`, `admin_command`, `sudo`, `group_change`, `password_reset` |
| `target` | TEXT | NO | Pseudonymous target account or resource reference |
| `result` | TEXT | NO | `success` or `failure` |
| `is_duplicate` | INTEGER | NO | Quality audit flag |

---

## 3. Context & Ground Truth Tables

### `context_events`
Benign business justification registry for context-aware risk dampening.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `context_id` | TEXT | NO (PK) | Unique context record UUID |
| `user_id` | TEXT | NO | Covered employee ID |
| `context_type` | TEXT | NO | `approved_travel`, `month_end_close`, `on_call`, `project_deadline`, `new_joiner`, `role_change` |
| `start_time` | TEXT | NO | ISO 8601 start timestamp |
| `end_time` | TEXT | NO | ISO 8601 end timestamp |
| `approved_by_role`| TEXT | NO | Authorizing authority (e.g., `Finance Manager`, `HR Director`) |
| `notes` | TEXT | YES | Free-text operational memo explaining the business exception |

---

### `ground_truth`
Synthetic scenario validation registry used by automated evaluation suites.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `scenario_id` | TEXT | NO (PK) | Scenario identifier (`S1`–`S8`) |
| `user_id` | TEXT | NO | Primary subject user ID |
| `start_time` | TEXT | NO | Injected scenario initiation |
| `end_time` | TEXT | NO | Injected scenario termination |
| `label` | TEXT | NO | `malicious_or_compromised` or `benign_exception` |
| `description` | TEXT | NO | Summary narrative of injected threat or benign exception |
| `expected_min_score`| REAL | NO | Floor score threshold for regression testing |
| `expected_max_score`| REAL | NO | Ceiling score threshold for regression testing |

---

## 4. Analytics, Baselines & Alerts

### `user_baselines`
Persisted rolling behavioral metrics computed per user.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `baseline_id` | TEXT | NO (PK) | UUID4 baseline record ID |
| `user_id` | TEXT | NO | Employee ID |
| `computed_date`| TEXT | NO | Computation anchor date (YYYY-MM-DD) |
| `baseline_type`| TEXT | NO | `user` or `role_peer` |
| `metric_name` | TEXT | NO | Feature key (`hour_histogram`, `download_median_bytes`, `known_countries`, etc.) |
| `metric_value` | TEXT | NO | Serialized JSON data structure or scalar numeric value |
| `confidence` | REAL | NO | Confidence metric $w \in [0.0, 1.0]$ based on sample size |

---

### `alerts`
Generated analytical risk findings.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `alert_id` | TEXT | NO (PK) | UUID4 alert identifier |
| `user_id` | TEXT | NO | Internal employee ID |
| `pseudonym_id` | TEXT | NO | Pseudonym token displayed in UI |
| `alert_date` | TEXT | NO | Evaluation date (YYYY-MM-DD) |
| `risk_score` | REAL | NO | Composite risk score $\in [0, 100]$ |
| `severity_band`| TEXT | NO | `low`, `medium`, `high`, `critical` |
| `indicators_json`| TEXT | NO | JSON array of triggered indicators, observed values, and evidence IDs |
| `context_applied_json`| TEXT | NO | JSON array of contextual reductions applied |
| `summary` | TEXT | NO | 2–4 sentence human-readable explanation |
| `baseline_confidence`| REAL | NO | Sample sufficiency weight at alert time |
| `status` | TEXT | NO | Review status: `open`, `confirmed_suspicious`, `benign_expected`, `false_positive` |
| `scenario_id` | TEXT | YES | Linked ground-truth scenario ID (if synthetic scenario match) |

---

## 5. Analyst Feedback & Cryptographic Audit Log

### `analyst_feedback`
Analyst review decisions and operational learning loop.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `feedback_id` | TEXT | NO (PK) | UUID4 feedback record ID |
| `alert_id` | TEXT | NO (FK) | Reference to reviewed alert |
| `analyst` | TEXT | NO | Analyst username |
| `verdict` | TEXT | NO | `confirmed_suspicious`, `benign_expected`, `needs_more_info`, `false_positive` |
| `comment` | TEXT | YES | Sanitized review notes (max 500 chars) |
| `created_at` | TEXT | NO | ISO 8601 UTC submission timestamp |

---

### `adjustment_rules`
Time-bounded analyst risk dampening rules resulting from `benign_expected` verdicts.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `rule_id` | TEXT | NO (PK) | UUID4 rule identifier |
| `user_id` | TEXT | NO | Covered employee ID |
| `indicator_id` | TEXT | NO | Target indicator name (e.g., `DOWNLOAD_VOLUME_SPIKE`) |
| `adjustment_factor`| REAL | NO | Multiplier applied to base severity (default 0.60) |
| `reason` | TEXT | NO | Analyst justification string |
| `created_by` | TEXT | NO | Analyst username |
| `created_at` | TEXT | NO | Rule issuance timestamp |
| `expires_at` | TEXT | NO | Expiration timestamp (default 30 days) |
| `is_active` | INTEGER | NO | Active status (1=active, 0=revoked/expired) |

---

### `audit_log`
Tamper-evident append-only cryptographic audit chain.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `entry_id` | TEXT | NO (PK) | UUID4 audit entry identifier |
| `timestamp` | TEXT | NO | ISO 8601 UTC timestamp |
| `actor` | TEXT | NO | Submitting identity (`system`, `analyst1`, etc.) |
| `action` | TEXT | NO | Operational event (`PIPELINE_RUN`, `REIDENTIFICATION_REQUEST`, `ANALYST_FEEDBACK`, etc.) |
| `details_json` | TEXT | NO | Canonical JSON payload of operational details |
| `prev_hash` | TEXT | NO | SHA-256 hash of previous log entry (Genesis: 64 zeros) |
| `entry_hash` | TEXT | NO | $\text{SHA-256}(\text{prev\_hash} + \text{canonical\_json}(\text{entry}))$ |

