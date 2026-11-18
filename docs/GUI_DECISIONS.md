# GUI Redesign & Architectural Decisions Log

This document records the audit of the legacy Streamlit interface, the mapping of every feature to the new "Casebook" editorial interface, and all architectural design decisions made during the redesign.

---

## 1. Audit of the Legacy Application (Step 0)

### Baseline Test Suite Status
- **Date/Time**: Baseline audit executed before GUI redesign.
- **Result**: 65 passed in 0.79s (`pytest tests/ -v`).
- **Detection Baseline**: Precision = 1.0, Recall = 1.0, F1 = 1.0, FPR = 0.0 across all S1–S8 injected scenarios.

### Page-to-Backend Audit Mapping

| Legacy Page | New Page | SQLite Tables Accessed | `src/ueba` Modules & Functions Called | Key User Actions & Data Exposed |
|---|---|---|---|---|
| **`1_Overview.py`** | **Today** (`/today` / `/`) | `alerts`, `users`, `analyst_feedback` | Read-only SQL queries via DB connection. | Aggregated open vs reviewed counts, critical/high breakdown, alert volume per day, departmental risk distribution, editorial summary statement. |
| **`2_Alert_Queue.py`** | **Inbox** (`/inbox`) | `alerts`, `users` | Read-only SQL queries via DB connection. | Triage queue sorted by risk score. Multi-filter by severity band, status, role, score slider. Keyboard navigation (`j`/`k`, `Enter`, `b`, `s`, `m`, `/`, `?`). |
| **`3_Alert_Detail.py`** | **Case** (`/case/{alert_id}`) | `alerts`, `users`, `login_events`, `download_events`, `file_access_events`, `privilege_events`, `context_events` | `src.ueba.feedback.submit_feedback`<br>`src.ueba.privacy.request_reidentification`<br>`src.ueba.audit.log_audit_event` | Narrative incident briefing, interactive timeline strip (with usual hours band), "Why this was flagged" indicator cards (observed vs usual bar pairs), context applied teal callout, score composition waterfall, analyst decision form (verdict, comments, 30-day adjustment rule), gated re-identification (senior_analyst role, ≥ 20 char reason). |
| **`4_User_Timeline.py`** | **People** (`/people`) | `users`, `login_events`, `download_events`, `privilege_events` | Read-only SQL queries via DB connection. | Pseudonym identity picker. 24h hour-of-day ribbon heat strip, daily download volume line vs typical range band, location history with first-seen timestamps, administrative privilege log. |
| **`5_Baselines.py`** | **Normal** (`/normal`) | `users`, `user_baselines` | `src.ueba.baseline` (stored baselines) | Per-user vs role-peer small multiples. Baseline confidence meter, cold-start explanation showing how days of history weight individual vs role baseline. |
| **`6_Scenarios_Demo.py`** | **Rehearsal** (`/rehearsal`) | `ground_truth`, `alerts`, `users` | Read-only SQL queries + evaluation scoring query. | S1–S8 chapter cards with narrative description, expected vs actual score, pass/fail status, and direct link to case. "Run all eight" automated evaluation. S4 vs S8 context comparison contrast. |
| **`7_Audit_Log.py`** | **Ledger** (`/ledger`) | `audit_log` | `src.ueba.audit.verify_audit_chain`<br>`src.ueba.audit.tamper_audit_entry` | Chronological immutable log table. Visual hash-chain continuity indicators, live SHA-256 chain verification button, simulated tamper testing, CSV export. Restricted to read-only for auditor role. |
| **`8_Privacy_and_Limitations.py`** | **Safeguards** (`/safeguards`) | System config (`config.yaml`) | `src.ueba.config.get_config` | Editorial reading view of `docs/PRIVACY.md` and `docs/LIMITATIONS.md` with 65-character line length. Live technical safeguards status panel (pseudonym salt, IP /24 mask, retention periods). |
| **`9_Model_Evaluation.py`** | **Evidence** (`/evidence`) | `ground_truth`, `alerts` | `src.ueba.evaluate.evaluate_against_ground_truth` | Confusion matrix (TP, FP, TN, FN), Precision, Recall, F1, FPR, score separation histogram, context dampening ablation study. Plain language readings under each chart. |

---

## 2. Design Decisions for the "Casebook" Editorial Desk

### GD-001 — Distinctive Visual Identity: The Case File
- **Rationale**: Security analysts suffer from alert fatigue exacerbated by alarming, flashing red dashboards with loud neon badges. The Casebook design adopts a calm, editorial aesthetic modeled after a thoughtful investigative casebook.
- **Palette**: Warm paper background (`#F6F2EA`), dark ink text (`#1E1B16`), warm muted ink (`#6B645A`), delicate hairline borders (`#D9D2C3`).
- **Accents**: Strictly two accents:
  1. *Attention Accent*: Warm Vermilion/Brick (`#C2410C`) used sparingly for items requiring urgent review.
  2. *Context Accent*: Deep Teal (`#1F5F5B`) reserved exclusively for "context applied / benign explained" items.
- **Dark Theme**: Warm charcoal (`#1B1915`) with warm ink borders (`#2D2923`) and paper text (`#EDE8DF`), respecting `prefers-color-scheme` with manual persistent override.
- **Typography**:
  - Headings & Editorial Prose: **Source Serif 4** (vendored locally).
  - UI Labels & Data Tables: **IBM Plex Sans** (vendored locally).
  - Event IDs, Timestamps, Byte Counts & Hashes: **IBM Plex Mono** (vendored locally).
  - Explicit avoidance of generic AI/SaaS fonts (Inter, Roboto, Poppins).

### GD-002 — Severity as Typography and Marks (Not Colored Pills)
- Severity is communicated through typographic weight, tabular numerals for the exact score, and distinct geometric marks (square fill patterns and hairline indicators) so the interface remains fully readable without color (WCAG AA and colorblind safe).

### GD-003 — Local Vendoring (Zero External Runtime Network Requests)
- In compliance with offline/air-gapped enterprise SOC environments, all JavaScript (D3.js v7) and web fonts (Source Serif 4, IBM Plex Sans, IBM Plex Mono in WOFF2) are vendored inside `gui/static/vendor/`. No CDNs or external web requests are made at runtime.

### GD-004 — Architecture: FastAPI + Vanilla Modular Web Components
- **Backend (`gui/server.py`)**: A lightweight, performant FastAPI server binding to `127.0.0.1`. All endpoints validate parameters using Pydantic and delegate writes to existing `src/ueba` functions (`submit_feedback`, `request_reidentification`, `verify_audit_chain`, `evaluate_against_ground_truth`).
- **Security & RBAC**:
  - Session CSRF tokens for state-modifying requests.
  - Server-side role enforcement (`analyst`, `senior_analyst`, `auditor`). Gated re-identification strictly requires `senior_analyst` and $\ge 20$ characters.
  - Strict output escaping via `textContent` or safe DOM manipulation.

### GD-005 — Preservation of the Legacy Streamlit Dashboard
- The legacy Streamlit application is preserved in `app_legacy/` for backward compatibility, while `run_demo.bat` and `run_demo.ps1` are updated to launch the new Casebook GUI.

---

## 3. Verification & Visual QA Results

### 3.1 Automated Visual QA Matrix
- **Automated Engine**: Playwright Chromium in headless mode (`tests/test_gui_visual_smoke.py`).
- **Viewports Tested**:
  1. Mobile (`390px x 844px`)
  2. Desktop Standard (`1280px x 900px`)
  3. Widescreen Workstation (`1920px x 1080px`)
- **Color Schemes Tested**:
  1. Light theme (warm paper `#F6F2EA`)
  2. Dark theme (warm charcoal `#1B1915`)
- **Total Screenshots Generated**: 60 high-resolution PNGs stored in `docs/screenshots/` (10 views x 2 themes x 3 viewports).
- **Console Errors Assertion**: 0 console errors across all navigation and interactive workflows.
- **External Request Assertion**: 0 external runtime network calls (verified via Playwright request monitoring).

### 3.2 Action Workflows Verified
1. **Analyst Decision Submission**: Submitted verdict (`benign_expected`) and comment via UI; verified database write and audit chain append.
2. **Cryptographic Chain Verification**: Tested "Check the Chain" UI button; verified 100% integrity validation across all chained records.
3. **Simulated Tamper Demonstration**: Tampered with audit record payload and confirmed that verification caught the exact broken link.
4. **Gated Re-Identification**: Validated senior analyst RBAC gate and $\ge 20$ character justification requirement.
5. **Keyboard Shortcuts**: Verified `j`/`k` navigation, `Enter` to open case, `b`/`s`/`m` quick verdicts, `/` focus search, and `?` help modal.

### 3.3 Test Suite Baseline Comparison
- **Original Baseline Tests**: 65 passed.
- **FastAPI Endpoint Tests**: 15 passed (`tests/test_gui_api.py`).
- **Playwright Visual Smoke**: 1 passed (`tests/test_gui_visual_smoke.py`).
- **Total Passing Tests**: 81 passed with 0 failures.
