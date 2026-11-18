# UEBA Platform — Test Scenarios (S1–S8 Ground Truth Specification)

This document provides complete end-to-end specifications for all synthetic scenarios injected into the UEBA platform detection period (Days 76–90). Each scenario validates specific detection capabilities, peer group baselines, contextual dampening, or credential protection mechanisms.

---

## Scenario Summary Table

| ID | Name | Ground Truth Label | Expected Score Range | Primary Detection Mechanism | Key Indicator(s) |
|---|---|---|---|---|---|
| **S1** | Compromised Credentials | `malicious_or_compromised` | **[80, 100] (Critical)** | Multi-stage killchain & anomaly chaining | `FAILED_LOGIN_BURST_THEN_SUCCESS`, `NEW_COUNTRY`, `UNUSUAL_HOUR`, `NEW_DEVICE`, `PRIVILEGE_ESCALATION_SEQUENCE`, `DOWNLOAD_VOLUME_SPIKE` |
| **S2** | Departing Employee Data Hoarding | `malicious_or_compromised` | **[65, 85] (High)** | Trend analysis & unauthorized destinations | `DOWNLOAD_TREND`, `DOWNLOAD_VOLUME_SPIKE`, `NEW_RESOURCE_ACCESS`, `RISKY_DESTINATION` |
| **S3** | Contractor Scope Creep | `malicious_or_compromised` | **[55, 75] (Medium/High)** | Peer group deviation & sensitivity boundary | `OUT_OF_ROLE_SENSITIVE_ACCESS`, `PEER_DEVIATION`, `OFF_HOURS_PRIVILEGE_USE` |
| **S4** | Approved Business Travel | `benign_exception` | **[0, 35] (Low)** | Context-aware dampening via approved record | `NEW_COUNTRY`, `NEW_CITY`, `UNUSUAL_HOUR` (all dampened 70%) |
| **S5** | Month-End Financial Close | `benign_exception` | **[0, 35] (Low)** | Calendar/business cycle context dampening | `DOWNLOAD_VOLUME_SPIKE`, `DOWNLOAD_TREND` (dampened 65%) |
| **S6** | New Joiner Cold Start | `benign_exception` | **[0, 45] (Low/Medium)** | Blended peer baseline & confidence discount | `NEW_RESOURCE_ACCESS`, `PEER_DEVIATION` (blended weight $w=0.15$) |
| **S7** | On-Call Emergency Maintenance | `benign_exception` | **[0, 35] (Low)** | Context dampening via active on-call shift | `OFF_HOURS_PRIVILEGE_USE`, `UNUSUAL_HOUR` (dampened 75%) |
| **S8** | Unapproved / Suspicious Travel | `malicious_or_compromised` | **[60, 80] (High)** | Negative control against S4 (no travel approval) | `NEW_COUNTRY`, `NEW_CITY`, `UNUSUAL_HOUR`, `NEW_DEVICE` (full weight) |

---

## Detailed Scenario Walkthroughs

### S1: Compromised Credentials (Developer Account)
- **Target User**: `E0001` (Developer, Engineering Department)
- **Injection Window**: Day 80, 02:45 UTC to 04:15 UTC
- **Narrative**: An external adversary executes a credential stuffing attack against the developer's SSO identity. After 8 rapid failed attempts from an anomalous IP range, the adversary gains access using stolen MFA session cookies. The actor connects from a foreign jurisdiction (Tokyo / UK), enrolls an unknown laptop device, executes administrative commands to escalate privilege, and exfiltrates 15 Restricted source code repositories (2.4 GB) to an external cloud staging share.
- **Injected Events**:
  - 8 × `login_events` (`auth_result='failure'`) within 4 minutes
  - 1 × `login_events` (`auth_result='success'`, `country='JP'`, `city='Tokyo'`, `device_id='DEV-ROGUE-99'`)
  - 2 × `privilege_events` (`action='role_grant'`, `action='admin_command'`, `target='iam_admin'`)
  - 15 × `file_access_events` targeting Restricted code repos
  - 3 × `download_events` (2.4 GB aggregate to `external_share`)
- **Score Calculation**:
  - Base points: `FAILED_LOGIN_BURST` (45) + `NEW_COUNTRY` (35) + `UNUSUAL_HOUR` (20) + `PRIVILEGE_ESCALATION` (55) + `DOWNLOAD_SPIKE` (40) + `RISKY_DESTINATION` (30)
  - Diminishing returns base: ~86 points
  - Chain bonus: `failed_login_then_privilege` (+10), `new_country_unusual_hour_bulk_download` (+15)
  - Result: **Risk Score 95–100 (Critical)**.

---

### S2: Departing Employee Data Hoarding (Sales Executive)
- **Target User**: `E0032` (Sales Executive, Commercial Accounts)
- **Injection Window**: Days 78–88 (10 consecutive days)
- **Narrative**: An enterprise sales director resigns and begins systematically copying client lists, pipeline forecasts, and competitor battlecards to a personal USB drive. Over 10 days, daily download volume accelerates monotonically from 25 MB to 850 MB/day, touching accounts and sales collateral outside their assigned vertical.
- **Injected Events**:
  - Daily download volumes scaling geometrically ($V_d = 25 \times 1.4^d$ MB)
  - 12 × `download_events` with `destination_type='personal_device'`
  - Access to 38 unassigned customer accounts in `crm_db`
- **Score Calculation**:
  - `DOWNLOAD_TREND` slope test ($p < 0.01$) + `DOWNLOAD_VOLUME_SPIKE` ($z_{MAD} > 4.2$) + `RISKY_DESTINATION` + `NEW_RESOURCE_ACCESS`
  - Result: **Risk Score 68–78 (High)**.

---

### S3: Contractor Scope Creep (External DevOps Specialist)
- **Target User**: `E0051` (Contractor, Cloud Operations)
- **Injection Window**: Day 82, 00:30 UTC to 03:00 UTC
- **Narrative**: An external contractor with legitimate access to infrastructure provisioning begins exploring confidential HR payroll records and internal finance ledgers far outside their contractual scope during nighttime hours.
- **Injected Events**:
  - 18 × `file_access_events` on `hr_records` and `payroll_db` (sensitivity: `Restricted`)
  - Off-hours session initiation outside standard contract window
- **Score Calculation**:
  - `OUT_OF_ROLE_SENSITIVE_ACCESS` (45 pts) + `PEER_DEVIATION` (25 pts) + `UNUSUAL_HOUR` (20 pts)
  - Diminishing returns result: **Risk Score 60–72 (Medium/High)**.

---

### S4: Approved Business Travel (Finance Manager) — *Benign Test Case*
- **Target User**: `E0018` (Senior Financial Analyst)
- **Injection Window**: Day 81 to Day 85
- **Narrative**: A finance analyst travels to London for quarterly budget consolidation. They log in from a hotel network in London at 07:30 BST (unusual relative to their home timezone in New York) on a secondary corporate laptop. 
- **Context Event**: `approved_travel` context record created by HR/Finance Director covering Days 80–86.
- **Dampening Behavior**:
  - Raw alerts triggered: `NEW_COUNTRY` (35 pts), `NEW_CITY` (15 pts), `UNUSUAL_HOUR` (20 pts), `NEW_DEVICE` (25 pts).
  - Raw score before dampening: ~62 (High).
  - Context dampening factor: 70% reduction across all 4 eligible indicators.
  - Adjusted points: $35 \times 0.3 = 10.5$, $15 \times 0.3 = 4.5$, $20 \times 0.3 = 6.0$, $25 \times 0.3 = 7.5$.
  - Result: **Risk Score 24–32 (Low)**. Alert remains visible in queue with clear label: *"Context applied: approved_travel"*.

---

### S5: Month-End Financial Close — *Benign Test Case*
- **Target Users**: Finance Team (`E0016`–`E0025`)
- **Injection Window**: Days 88–90 (Final 3 days of calendar month)
- **Narrative**: The finance department generates and downloads comprehensive ledger reports, audit extracts, and reconciliation sheets, generating 8× typical daily volume and working late into the night.
- **Context Event**: Scheduled `month_end_close` window active for all users with `role='Finance'`.
- **Dampening Behavior**:
  - Raw triggers: `DOWNLOAD_VOLUME_SPIKE` ($z_{MAD} = 5.8$), `DOWNLOAD_TREND`, `UNUSUAL_HOUR`.
  - Context factor: 65% reduction applied to volume and hour indicators.
  - Result: **Risk Score 22–31 (Low)**.

---

### S6: New Joiner Cold Start — *Benign Test Case*
- **Target User**: `E0060` (Junior Developer, Hired 5 days before detection period)
- **Injection Window**: Days 85–90
- **Narrative**: A newly hired engineer explores documentation, checks out multiple repositories, and downloads build packages. With only 5 days of history, a traditional anomaly detector would trigger extreme false positives.
- **Baseline Solution**:
  - Baseline confidence $w = \min(1.0, 5/30) = 0.17$.
  - Effective baseline is 83% derived from Developer peer-group norm.
  - New joiner context dampening (60% discount) softens exploratory alerts.
  - Result: **Risk Score 28–38 (Low/Medium)**.

---

### S7: On-Call Emergency Maintenance — *Benign Test Case*
- **Target User**: `E0045` (IT Systems Administrator)
- **Injection Window**: Day 83, 02:15 UTC
- **Narrative**: An on-call systems administrator logs in at 02:15 AM to restart a crashed database daemon, invoking sudo and administrative CLI commands.
- **Context Event**: Active `on_call` roster record for `E0045`.
- **Dampening Behavior**:
  - Raw triggers: `OFF_HOURS_PRIVILEGE_USE` (35 pts), `UNUSUAL_HOUR` (20 pts).
  - Context factor: 75% reduction applied.
  - Result: **Risk Score 18–28 (Low)**.

---

### S8: Unapproved / Suspicious Travel — *Negative Control vs S4*
- **Target User**: `E0022` (Finance Analyst)
- **Injection Window**: Day 81 to Day 85
- **Narrative**: Identical activity pattern to S4 (login from foreign country, unusual hours, new device), but **without any approved travel record** in the context registry.
- **Result Comparison**:
  - S4 (with travel context): **Risk Score ~28 (Low)**.
  - S8 (without travel context): **Risk Score ~66 (High)**.
  - **Delta**: $+38$ points separation, proving that risk dampening is driven strictly by verified contextual evidence rather than blanket heuristic suppression.

