# UEBA Platform — Architecture

## Overview

The UEBA (User and Entity Behaviour Analytics) Platform is a full-stack, locally-deployable insider-threat detection system built in Python.  It combines rule-based behavioural indicators, context-aware dampening, analyst feedback loops, and a supporting ML signal into a transparent, auditable risk-scoring engine.

The platform is intentionally designed to be **explainable first**: every risk score can be traced back to specific events and behavioural baselines.  The ML component (Isolation Forest) adds weight but never overrides the rule-based findings.

---

## High-Level Architecture

```mermaid
flowchart TD
    subgraph Generation["🏭 Synthetic Data Generation"]
        ORG["org.py\nOrg & Role Structure"]
        NORMAL["normal.py\nBaseline Events"]
        SCENARIOS["scenarios.py\nThreat Scenarios ×8"]
        CONTEXT_GEN["context.py\nContext Signals"]
        BUILD["build_dataset.py\nOrchestrator"]
        ORG --> BUILD
        NORMAL --> BUILD
        SCENARIOS --> BUILD
        CONTEXT_GEN --> BUILD
    end

    subgraph Storage["💾 Storage Layer"]
        CSV["data/*.csv\nRaw Files"]
        DB["data/ueba.db\nSQLite Database"]
        BUILD --> CSV
        CSV --> INGEST
        INGEST --> DB
    end

    subgraph Pipeline["⚙️ Detection Pipeline"]
        INGEST["ingest.py\nSchema Validate & Ingest"]
        BASELINE["baseline.py\nRolling Baselines"]
        FEATURES["features.py\nFeature Engineering"]
        INDICATORS["indicators.py\n15 Rule-Based Indicators"]
        ML["ml_signal.py\nIsolation Forest"]
        SCORING["scoring.py\nRisk Score + Chain Bonuses"]
        DAMPENING["context_dampening.py\nContext Reduction"]
        FEEDBACK["feedback.py\nAnalyst Adjustments"]
        DB --> BASELINE
        DB --> FEATURES
        BASELINE --> FEATURES
        FEATURES --> INDICATORS
        FEATURES --> ML
        INDICATORS --> SCORING
        ML --> SCORING
        SCORING --> DAMPENING
        DAMPENING --> FEEDBACK
        FEEDBACK --> DB
    end

    subgraph Dashboard["🖥️ Streamlit Dashboard"]
        APP["streamlit_app.py\nEntry Point"]
        OV["1_Overview"]
        AQ["2_Alert_Queue"]
        AD["3_Alert_Detail"]
        UT["4_User_Timeline"]
        BL["5_Baselines"]
        SD["6_Scenarios_Demo"]
        AL["7_Audit_Log"]
        PL["8_Privacy_&_Limitations"]
        ME["9_Model_Evaluation"]
        APP --> OV & AQ & AD & UT & BL & SD & AL & PL & ME
    end

    subgraph CrossCutting["🔒 Cross-Cutting Concerns"]
        PRIVACY["privacy.py\nPseudonymisation"]
        AUDIT["audit.py\nImmutable Audit Chain"]
        CONFIG["config.py\nTyped Settings"]
        EVAL["evaluate.py\nMetrics & AUROC"]
    end

    DB --> APP
    FEEDBACK --> AUDIT
    INDICATORS --> AUDIT
    Pipeline --> EVAL
```

---

## Component Descriptions

### Data Generation Layer
| Module | Responsibility |
|--------|---------------|
| `org.py` | Builds the synthetic organisation: 60 employees across 5 departments, 10 contractors, role-to-resource permission maps |
| `normal.py` | Generates 90 days of realistic events (logins, downloads, file access, privilege use) for each user following role-appropriate patterns |
| `scenarios.py` | Injects 8 distinct insider-threat patterns into the event stream after day 75 |
| `context.py` | Generates contextual signals: travel approvals, on-call schedules, project deadlines, role changes |
| `build_dataset.py` | Orchestrates generation and writes outputs to `data/` |

### Storage Layer
- **SQLite** (`data/ueba.db`): Primary store for events, baselines, alerts, feedback, and the audit chain.
- **CSV files** (`data/`): Raw generated data, importable into external tools.

### Detection Pipeline
| Module | Responsibility |
|--------|---------------|
| `ingest.py` | Schema-validates and ingests CSV events; supports incremental watermark-based ingestion |
| `baseline.py` | Computes rolling 60-day per-user behavioural baselines with confidence weighting |
| `features.py` | Engineers temporal, geographic, volumetric, access, and peer-deviation features |
| `indicators.py` | 15 rule-based indicators producing `IndicatorHit` objects with evidence |
| `ml_signal.py` | Trains/scores Isolation Forest; output is ML_ANOMALY_SUPPORT indicator only |
| `scoring.py` | Aggregates hits into 0–100 risk scores, applies chain bonuses |
| `context_dampening.py` | Reduces scores for legitimate contextual explanations |
| `feedback.py` | Applies analyst feedback adjustments with time-limited expiry |
| `pipeline.py` | End-to-end orchestrator |

### Dashboard (Streamlit)
Nine pages covering: system overview, alert triage queue, per-alert deep-dive, user event timeline, baseline inspection, scenario walkthrough, audit log viewer, privacy controls, and evaluation metrics.

### Cross-Cutting Concerns
- **privacy.py**: Pseudonymisation via HMAC-SHA256, IP truncation, role-gated identity resolution
- **audit.py**: SHA-256 chained audit log for tamper detection
- **config.py**: Pydantic settings loaded from YAML + environment variables
- **evaluate.py**: Precision, recall, F1, AUROC against ground-truth scenario labels

---

## Data Flow

```mermaid
sequenceDiagram
    participant G as Generator
    participant DB as SQLite DB
    participant P as Pipeline
    participant D as Dashboard
    participant A as Analyst

    G->>DB: Synthetic events + context signals
    P->>DB: Read events (watermark-based)
    P->>P: Compute baselines → features → indicators → scores
    P->>DB: Write alerts + audit entries
    D->>DB: Query alerts + baselines
    A->>D: Review alert, submit feedback
    D->>DB: Write feedback + audit entry
    P->>P: Next run: apply feedback adjustments
```

---

## Scoring Pipeline Detail

```mermaid
flowchart LR
    H["IndicatorHit List"] --> RAW["raw_score =\nΣ(base_points × confidence_weight)"]
    RAW --> CB["+ Chain Bonus\n(correlated indicator sets)"]
    CB --> CAP["Cap at 100"]
    CAP --> DAMP["× Context Dampening Factor\n(0.50 – 0.80 reduction)"]
    DAMP --> FADJ["× Feedback Adjustment\n(expiring, up to 0.60)"]
    FADJ --> FINAL["Final Score → Risk Band"]
```

---

## Technology Choices

| Choice | Rationale |
|--------|-----------|
| Python 3.11+ | Wide library ecosystem, type hints, async support |
| SQLite | Zero-setup, file-portable, sufficient for demo scale |
| Streamlit | Rapid data-app development; no frontend build step |
| Plotly | Interactive, embeds cleanly in Streamlit |
| Isolation Forest | Unsupervised, no labels needed, interpretable anomaly scores |
| Pydantic v2 | Typed config validation, fast, composable |
| HMAC-SHA256 | Standard pseudonymisation primitive; reversible only with salt |
| Chained SHA-256 audit | Lightweight tamper detection without a blockchain |
