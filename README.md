# Insider Threat Detection and User Behavior Analytics (UEBA) Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg)](https://www.sqlite.org/)

An explainable, privacy-preserving, and context-aware **User and Entity Behavior Analytics (UEBA)** prototype designed to detect anomalous insider activity, account compromise, and data exfiltration while minimizing false positives and protecting employee dignity.

> [!IMPORTANT]
> **Core Principle:** An anomaly is **NOT** proof of wrongdoing. All findings are labeled as "unusual indicator" or "needs review"—never "guilty" or "malicious user". Benign-exception handling is a first-class architectural capability.

---

## 1. Problem & Solution Overview

### The Problem
Insider threats account for some of the most expensive and damaging security breaches. However, conventional monitoring approaches fail:
- **Alert Fatigue:** Rules that trigger on simple thresholds flag legitimate operations (e.g., month-end accounting, scheduled on-call shifts, or approved international travel).
- **Privacy Violations:** Invasive surveillance (keyloggers, screen recording) violates labor laws, works council agreements, GDPR, and India's DPDP Act.
- **Black-Box Confusion:** Pure machine learning systems output arbitrary risk numbers without actionable, event-level justification.

### The Solution
Our UEBA platform introduces four core innovations:
1. **Explainable Indicator Cards:** Every alert decomposes into specific rule-based indicators linking directly to raw audit event IDs.
2. **Context-Aware Risk Dampening:** Automatically correlates activity with business calendars (approved travel, month-end close, on-call schedules), mathematically dampening alert severity while maintaining transparent audit trails.
3. **Blended Peer Baselines:** Solves the cold-start dilemma for new hires by dynamically blending individual baselines with role-peer norms.
4. **Cryptographic Tamper-Evident Audit:** Uses an immutable SHA-256 hash chain to record all analyst reviews, config updates, and identity re-identifications.

---

## 2. Architecture Diagram

```mermaid
flowchart TD
    subgraph Ingestion["1. Synthetic Data & Ingestion"]
        GEN["Deterministic Event Generator\n(60 Users, 150 Resources, 90 Days)"]
        VAL["Pydantic Data Validator &\nIP Truncation (/24)"]
        DB[("SQLite Database\n(ueba.db)")]
        GEN --> VAL --> DB
    end

    subgraph Baselines["2. Baseline & Behavioral Profiling"]
        USER_BL["Rolling User Baseline\n(Median & MAD Statistics)"]
        PEER_BL["Role-Peer Baseline\n(Departmental Norms)"]
        BLEND["Confidence-Weighted Blending\n(Cold-Start Resolution)"]
        DB --> USER_BL & PEER_BL
        USER_BL & PEER_BL --> BLEND
    end

    subgraph Analytics["3. Explainable Detection Engine"]
        IND["13+ Rule-Based Indicators\n(Hours, Volume, Geo, Privilege)"]
        ML["Isolation Forest ML Signal\n(Secondary Check, max 15 pts)"]
        CHAIN["Attack Chain Bonuses\n(Correlated Killchains)"]
        BLEND --> IND
        DB --> IND & ML
        IND & ML --> CHAIN
    end

    subgraph Dampening["4. Context & Benign Handling"]
        CTX[("Business Context Registry\n(Travel, Month-End, On-Call)")]
        DAMP["Context Dampening Engine\n(Caps Reduction, Never Silently Suppresses)"]
        CHAIN --> DAMP
        CTX --> DAMP
    end

    subgraph Presentation["5. Actionable SOC Interface"]
        APP["Streamlit SOC Dashboard"]
        DETAIL["Hero Alert Detail &\nScore Waterfall Chart"]
        FEEDBACK["Analyst Feedback Loop &\n30-Day Adjustment Rules"]
        AUDIT["SHA-256 Cryptographic\nAudit Ledger"]
        DAMP --> APP
        APP --> DETAIL
        DETAIL --> FEEDBACK
        FEEDBACK --> AUDIT
    end
```

---

## 3. Quick Start (Windows)

The platform is completely self-contained and requires no Docker, external databases, or paid APIs.

### Option A: One-Click Windows Batch
Open Command Prompt and run:
```cmd
run_demo.bat
```

### Option B: PowerShell
```powershell
.\run_demo.ps1
```

### Option C: Manual CLI Execution
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize environment variables
Copy-Item .env.example .env

# 4. Generate 90 days of synthetic data and inject S1-S8 scenarios
python -m src.ueba.generator.build_dataset

# 5. Execute baseline and detection pipeline
python -m src.ueba.pipeline

# 6. Launch the Streamlit dashboard
streamlit run app/streamlit_app.py
```
Open **http://localhost:8501** in your browser.

---

## 4. Test Suite Execution

Run all 65 unit and end-to-end integration tests using `pytest`:

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

To run with coverage reporting:
```powershell
.\.venv\Scripts\python -m pytest tests/ --cov=src/ueba --cov-report=term-missing
```

---

## 5. Repository Structure

```
ueba-platform/
  README.md                          # Executive overview, architecture, quick start
  requirements.txt                   # Pinned open-source dependencies
  run_demo.bat                       # One-click Windows CMD launcher
  run_demo.ps1                       # One-click Windows PowerShell launcher
  .env.example                       # Template for secrets (PSEUDONYM_SALT)
  .gitignore                         # Git exclusion rules
  config/
    config.yaml                      # Engine thresholds, retention, and weights
    scoring_weights.yaml             # Per-indicator point values and explanations
  data/                              # SQLite database (ueba.db) and CSV exports
  docs/
    ARCHITECTURE.md                  # Comprehensive system architecture & scaling
    PRIVACY.md                       # Data minimization, pseudonymization, GDPR/DPDP
    LIMITATIONS.md                   # Realism gaps, poisoning risk, ML constraints
    TEST_SCENARIOS.md                # Specifications for scenarios S1 through S8
    DATA_DICTIONARY.md               # Complete database schema reference
    DECISIONS.md                     # Architectural Decision Records (ADR)
    DEMO_SCRIPT.md                   # 5-minute timed presentation pitch script
    JUDGING_MAP.md                   # Matrix mapping criteria to code evidence
  src/ueba/
    config.py                        # Pydantic configuration validation
    privacy.py                       # HMAC-SHA256 pseudonymization, IP truncation
    db.py                            # SQLite schema, connection pool, and migrations
    baseline.py                      # Per-user and peer-role rolling baselines
    features.py                      # Daily feature extraction
    indicators.py                    # 13+ explainable behavioral indicators
    ml_signal.py                     # Supporting IsolationForest anomaly scorer
    scoring.py                       # Diminishing returns & chaining engine
    context_dampening.py             # Context-aware benign reduction logic
    feedback.py                      # Analyst verdict recording & adjustment rules
    audit.py                         # Cryptographic SHA-256 hash chain
    evaluate.py                      # Ground-truth accuracy and evaluation metrics
    pipeline.py                      # Orchestrator CLI
    generator/
      org.py                         # User, department, shift, and resource generator
      normal.py                      # 90-day background activity simulation
      scenarios.py                   # Injected ground-truth attack/benign scenarios
      context.py                     # Travel, month-end, and on-call scheduler
      build_dataset.py               # Data generator entry point
  app/
    streamlit_app.py                 # Multi-page navigation & role switcher
    components.py                    # Shared UI widgets, banners, and metric cards
    pages/
      1_Overview.py                  # Executive KPI dashboard & risk distribution
      2_Alert_Queue.py               # Filterable triage table
      3_Alert_Detail.py              # Hero page: indicator waterfall, evidence, review
      4_User_Timeline.py             # User behavioral timeline & activity maps
      5_Baselines.py                 # User vs Role peer comparison radar
      6_Scenarios_Demo.py            # Live S1-S8 demo runner with pass/fail badges
      7_Audit_Log.py                 # Cryptographic ledger viewer & verification
      8_Privacy_and_Limitations.py   # Rendered policy & technical boundaries
      9_Model_Evaluation.py          # Ground-truth confusion matrix & metrics
  tests/
    test_generator.py                # Validation of org and synthetic generators
    test_baseline.py                 # Non-leakage and baseline blending tests
    test_indicators.py               # Unit tests for each detection indicator
    test_scoring.py                  # Diminishing returns & chain bonus math
    test_context_dampening.py        # Context dampening factor validation
    test_privacy.py                  # HMAC, IP truncation, and XSS sanitization
    test_audit_chain.py              # Cryptographic chain & tamper-detection tests
    test_feedback.py                 # Analyst learning loop & rule lifecycle
    test_scenarios.py                # End-to-end S1-S8 ground-truth assertions
```

---

## 6. Dashboard Preview (Screenshots & Capabilities)

| Dashboard View | Primary Security Analyst Capability |
|---|---|
| **Overview (`1_Overview.py`)** | Global SOC posture, severity breakdown, alert distribution, and departmental risk heatmaps. |
| **Alert Queue (`2_Alert_Queue.py`)** | Interactive triage queue filterable by severity, status, role, date, and indicator type. |
| **Alert Detail (`3_Alert_Detail.py`)** | **The Hero View**: Score composition waterfall chart, explainable indicator cards, exact triggering event IDs, and the analyst verdict review form. |
| **Scenarios Demo (`6_Scenarios_Demo.py`)** | Single-click execution of scenarios S1–S8 demonstrating real-time contrast between malicious and benign context-dampened cases. |
| **Audit Log (`7_Audit_Log.py`)** | Interactive verification of the SHA-256 hash chain with instant tamper detection. |
| **Model Evaluation (`9_Model_Evaluation.py`)** | Complete confusion matrix, Precision/Recall/F1 metrics, and ablation study demonstrating the value of context dampening. |

---

## 7. License
This project is open-source under the [MIT License](LICENSE). Built for academic, demonstration, and evaluation purposes.

