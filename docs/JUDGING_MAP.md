# UEBA Platform — Judging Criteria Map

This document explicitly maps the four competition judging criteria (Innovation 25%, Technical Excellence 25%, Feasibility & Real-World Applicability 25%, Presentation & Polish 25%) directly to concrete features, architectural decisions, and source files within the project repository.

---

## 1. Innovation (25% Weight)

| Innovation Pillar | Description | Primary Code Implementation | Supporting Documentation |
|---|---|---|---|
| **Context-Aware Risk Dampening** | Traditional UEBA treats all anomalies as threats. Our platform treats business context (approved travel, month-end close, on-call shifts, project deadlines) as a mathematical dampening factor that reduces alert severity without silently removing audit visibility. | `src/ueba/context_dampening.py`<br>`src/ueba/generator/context.py` | `docs/ARCHITECTURE.md`<br>`docs/TEST_SCENARIOS.md` (S4 vs S8) |
| **Cold-Start Blended Baselines** | New hires lack behavioral history. Rather than triggering high false-positive alerts, we dynamically blend the individual's baseline with their role-peer group baseline using a confidence weight $w \in [0, 1]$ based on data volume. | `src/ueba/baseline.py` (`blend_baselines`) | `docs/ARCHITECTURE.md`<br>`docs/LIMITATIONS.md` |
| **Diminishing Returns & Chaining** | Multi-indicator aggregation uses a non-saturating formula $100 \cdot (1 - \prod(1 - p_i/100))$ combined with domain-specific chain bonuses for correlated attack patterns (e.g. credential attack + privilege escalation). | `src/ueba/scoring.py` (`_diminishing_returns_score`, `_apply_chain_bonuses`) | `docs/DECISIONS.md`<br>`config/scoring_weights.yaml` |
| **Analyst Learning Loop with Expiry** | When an analyst marks an alert `benign_expected`, the platform creates a time-bounded (30-day) adjustment rule for that user and indicator, preventing alert fatigue while avoiding permanent blind spots. | `src/ueba/feedback.py` (`_create_adjustment_rule`, `expire_old_rules`) | `docs/ARCHITECTURE.md`<br>`app/pages/3_Alert_Detail.py` |

---

## 2. Technical Excellence (25% Weight)

| Technical Dimension | Implementation Details | Evidence in Codebase | Verification Method |
|---|---|---|---|
| **Cryptographic Tamper-Evident Audit** | Append-only ledger where every entry stores $\text{SHA256}(\text{prev\_hash} + \text{canonical\_json}(\text{entry}))$. Full chain verification detects single-character tampering. | `src/ueba/audit.py` (`log_audit_event`, `verify_audit_chain`) | `tests/test_audit_chain.py` (explicit test deliberately tampers with row to verify detection) |
| **Zero Data Leakage** | Baselines computed for day $D$ strictly use timestamps $< D$. Strict temporal separation ensures model training validity. | `src/ueba/baseline.py`<br>`src/ueba/pipeline.py` | `tests/test_baseline.py` (`test_no_data_leakage`) |
| **Robust Statistics (MAD / Median)** | Replaced standard deviation with Median Absolute Deviation (MAD) for download volume and event frequency to withstand outlier contamination. | `src/ueba/baseline.py`<br>`src/ueba/indicators.py` | `tests/test_indicators.py` (`test_download_spike_fires`) |
| **Data Quality & Sanitization** | Pydantic data schemas validate all inputs. Ingest pipeline gracefully detects, repairs, or logs duplicate events and missing optional fields. | `src/ueba/config.py`<br>`src/ueba/privacy.py` (`sanitize_comment`) | `tests/test_privacy.py` (XSS sanitization, length limits) |
| **Deterministic Data Generation** | Seeded random generation (`seed=42`) creates reproducible org graphs, shifts, noise, and 8 distinct test scenarios across 90 days. | `src/ueba/generator/org.py`<br>`src/ueba/generator/normal.py` | `tests/test_generator.py` (`test_org_deterministic`) |

---

## 3. Feasibility & Real-World Applicability (25% Weight)

| Feasibility Pillar | Enterprise Requirement | How the Platform Solves It | Source Reference |
|---|---|---|---|
| **Strict Data Minimization & Privacy** | Compliance with GDPR, India DPDP Act, and works council agreements prohibiting workplace spyware. | No full IPs (truncated to `/24`), no names or emails in analytics DB, HMAC-SHA256 pseudonymization. | `src/ueba/privacy.py`<br>`docs/PRIVACY.md` |
| **Separation of Duties** | Re-identification must be strictly restricted to senior authorized roles with audit logging. | Identity mapping lives in separate table. Re-identification requires role `senior_analyst`, minimum 20-character justification, and logs a tamper-evident audit record. | `src/ueba/privacy.py` (`request_reidentification`)<br>`app/pages/3_Alert_Detail.py` |
| **Transparent Limitations** | Acknowledging boundaries honestly builds enterprise security trust. | Comprehensive documentation of synthetic realism gaps, baseline poisoning risks, and ML secondary role. | `docs/LIMITATIONS.md`<br>`app/pages/8_Privacy_and_Limitations.py` |
| **Data Retention & Lifecycle** | Legal compliance requires automated data expiration. | Configurable retention periods (90d events, 365d alerts) with programmatic purge function. | `src/ueba/privacy.py` (`purge_expired_events`) |
| **Zero-Cost, Portable Stack** | No reliance on costly cloud subscriptions, proprietary APIs, or heavy infrastructure. | Standard Python, SQLite with parameterized SQL, Streamlit, Scikit-Learn, Plotly. | `requirements.txt`<br>`run_demo.bat` |

---

## 4. Presentation & Polish (25% Weight)

| Aspect | User Interface & Experience Feature | Relevant File / Page |
|---|---|---|
| **Synthetic Demo Banner** | Prominent, persistent "SYNTHETIC DATA - DEMO ONLY" notification across all views. | `app/components.py`<br>`app/streamlit_app.py` |
| **Executive Overview** | Metric cards (Total Alerts, Severity Breakdown, Review Progress), Risk Score Distribution histogram, Alert Volume Timeline, Department Risk Heatmap. | `app/pages/1_Overview.py` |
| **Interactive Alert Queue** | Filterable by severity, review status, role, date, and indicator type with color-coded risk badges. | `app/pages/2_Alert_Queue.py` |
| **Hero Alert Detail Page** | Score breakdown waterfall chart, explainable indicator cards with observed vs baseline values and event IDs, interactive event timeline, and analyst review modal. | `app/pages/3_Alert_Detail.py` |
| **Scenarios Demo (Pitch Core)** | One-click execution of S1–S8 test cases with expected vs actual scores and live pass/fail badges. | `app/pages/6_Scenarios_Demo.py` |
| **Interactive Audit Verification** | Live button triggering real-time cryptographic verification of the SHA-256 audit ledger with export capability. | `app/pages/7_Audit_Log.py` |
| **Model Evaluation Suite** | Ground-truth confusion matrix, Precision/Recall/F1 metrics, score separation charts, and ablation study demonstrating context dampening value. | `app/pages/9_Model_Evaluation.py` |
| **Documentation Completeness** | 8 comprehensive Markdown guides with zero TODOs or placeholders. | `docs/*.md`<br>`README.md` |

