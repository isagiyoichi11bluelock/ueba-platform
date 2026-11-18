# UEBA Platform — Design Decisions Log

This document records significant architectural and design decisions made during the platform's development, including the options considered and the rationale for each choice.

---

## DD-001 — SQLite as Primary Store

**Date**: Project inception  
**Decision**: Use SQLite for the local database layer.  
**Alternatives considered**: PostgreSQL, DuckDB, Parquet-only  
**Rationale**:
- Zero-infrastructure setup: runs on a laptop without a database server
- File-portable: the entire dataset can be copied or emailed as a single `.db` file
- Python `sqlite3` is in the standard library — no extra install
- Adequate for the demo scale (< 500,000 events, single writer)
- DuckDB was tempting for analytics performance but adds a dependency and its write story is more complex; Parquet alone would have required re-implementing query logic

**Trade-off accepted**: Not suitable for concurrent writes or > 1M events/day.  Documented in LIMITATIONS.md §12.

---

## DD-002 — Isolation Forest as the ML Component

**Date**: Project inception  
**Decision**: Use scikit-learn's `IsolationForest` as the sole ML anomaly detector, as a supporting signal only.  
**Alternatives considered**: Autoencoder, One-Class SVM, LSTM sequence model, Gaussian Mixture Model  
**Rationale**:
- Unsupervised: requires no labelled training data, which is realistic (most orgs have no clean insider-threat labels)
- Scales sub-linearly with dataset size (ensemble of random trees)
- Interpretable at the indicator level: its score is mapped to a single binary supporting indicator (ML_ANOMALY_SUPPORT, 15 pts), not the primary driver of risk
- Autoencoders and LSTMs would require GPU infrastructure and much larger datasets to outperform
- One-Class SVM does not scale to high-dimensional inputs without careful kernel tuning
- The "supporting signal only" design constraint prevents the ML score from silently dominating results — security analysts, auditors, and review panels can always audit the rule-based contributors

**Trade-off accepted**: No feature-level explanation for the ML signal.  Documented in LIMITATIONS.md §17.

---

## DD-003 — Rule-Based Indicators as Primary Signal

**Date**: Project inception  
**Decision**: 15 hand-crafted rule-based indicators are the primary risk contributors.  ML is capped at 15 base points.  
**Rationale**:
- Explainability: every score can be traced to a specific event and behavioural baseline deviation
- Auditability: rules can be reviewed and challenged by legal/compliance teams
- Precision: rules encode domain knowledge that unsupervised ML cannot reliably learn from 90 days of data
- Operational trust: analysts who understand rules are more likely to act on them

---

## DD-004 — Context Dampening Architecture

**Date**: Early design  
**Decision**: Context dampening is a **post-scoring** multiplicative factor, not a pre-filter that suppresses indicators.  
**Alternatives considered**: Suppress indicators before scoring; adjust indicator base points  
**Rationale**:
- Pre-filtering would erase evidence from the audit trail ("we saw it but ignored it")
- Post-scoring dampening records the full raw score alongside the reduced final score, providing a complete evidence trail for review
- Multiplicative rather than additive dampening is bounded and predictable: factors compose naturally and the result is always in [0, raw_score]
- Some indicators (IMPOSSIBLE_TRAVEL, FAILED_LOGIN_BURST_THEN_SUCCESS) are immune to dampening by design — these represent direct access control failures or impossible physics that no business context excuses

---

## DD-005 — Feedback Expiry

**Date**: Early design  
**Decision**: Analyst feedback adjustments expire after 30 days.  
**Rationale**:
- Stale feedback: an analyst marks a user as false-positive; 6 months later that user begins exfiltrating data.  Without expiry, the feedback suppresses genuine alerts indefinitely.
- 30 days is long enough to clear the typical false-positive cluster from approved travel or a known project push
- Feedback is always visible in the audit log regardless of expiry, so there is no information loss

---

## DD-006 — Streamlit for the Dashboard

**Date**: Project inception  
**Decision**: Use Streamlit with its native multi-page architecture (pages/ directory).  
**Alternatives considered**: Dash (Plotly), Flask + React, Gradio  
**Rationale**:
- Minimal boilerplate: a data-science team can iterate on pages without front-end build tooling
- Native multi-page support in Streamlit 1.28+ maps cleanly to the 9-page navigation structure
- Plotly integrates natively with Streamlit for interactive charts
- Dash has richer layout control but requires more code for basic navigation; Flask+React would be a full-stack project in itself

**Trade-off accepted**: Streamlit's execution model (re-runs on every interaction) can be slow for large DataFrames without `@st.cache_data` decorators.

---

## DD-007 — Pseudonymisation via HMAC-SHA256

**Date**: Privacy design sprint  
**Decision**: Use HMAC-SHA256 keyed on a per-deployment salt for pseudonymisation.  
**Alternatives considered**: UUID mapping table, format-preserving encryption (FPE), bcrypt  
**Rationale**:
- Stability without a mapping table: same input + same salt = same pseudonym, deterministically
- A mapping table is a single point of compromise and grows unboundedly
- bcrypt is designed to be slow (key-stretching), which is valuable for passwords but adds latency for high-volume pseudonymisation
- FPE (e.g. FF3-1) preserves format but requires a block cipher key; HMAC is simpler and well-understood
- The hex digest is truncated to a short numeric suffix for readability (e.g. `U-0042`)

---

## DD-008 — Chained SHA-256 Audit Log

**Date**: Privacy design sprint  
**Decision**: Each audit log record includes a SHA-256 checksum of its content concatenated with the previous record's checksum.  
**Alternatives considered**: Signed log entries (RSA/ECDSA), external blockchain, plain append-only table  
**Rationale**:
- A plain append-only table with no integrity check can be silently tampered with by anyone with database access
- A blockchain is overkill for a single-organisation audit log and introduces external dependencies
- Digital signatures (RSA/ECDSA) require key management infrastructure
- A chained hash is a well-understood, lightweight tamper-detection primitive — sufficient for demonstrating the principle and meeting reasonable audit requirements in a demo

**Trade-off accepted**: The chain can be rebuilt from scratch by an adversary who has full DB write access and replays all records.  A production system should anchor chain roots in an external, append-only log service.

---

## DD-009 — Scoring Bands

**Date**: Scoring design  
**Decision**: Four risk bands: Low (0–34), Medium (35–59), High (60–79), Critical (80–100).  
**Rationale**:
- Three bands (low/medium/high) is common but conflates very high-confidence detections with moderate ones
- Five or more bands would require more calibration work and analyst confusion around threshold differences
- Critical band (80–100) is intentionally narrow: only highly correlated, multi-indicator events with minimal dampening should reach it, reducing alert fatigue at the top tier

---

## DD-010 — Confidence Weighting

**Date**: Baseline design  
**Decision**: Each indicator hit is multiplied by a confidence weight derived from days of observation and event count in the baseline window.  
**Rationale**:
- A user who joined 3 days ago has an almost empty baseline; firing a high-confidence alert based on 3 events would be noisy and unfair
- Confidence grows linearly until `min_days_for_full_confidence` (30 days) AND `min_events_for_full_confidence` (50 events) are both met
- New joiners automatically attract lower scores, but they also receive a `new_joiner` context signal that further dampens scores (DD-004 interaction)

---

## DD-011 — Enterprise Asset & Location Baseline Grounding

**Date**: Implementation optimization  
**Decision**: Seed device and country baselines with officially assigned hardware inventory (`devices` table) and HR record home office location (`users` table).  
**Alternatives considered**: Purely observational baseline from historic login logs only.  
**Rationale**:
- A newly onboarded employee logging in on Day 1 using their corporate-issued laptop from their registered home location is not an anomaly — it is expected business activity.
- Purely observational baselines flag new devices and new countries on day 1 for any user with limited history (cold start).
- Integrating enterprise asset management (IT device register) and HR directory records reflects real-world enterprise architectures where authoritative identity/asset data grounds behavioural baselines.

---

## DD-012 — Python 3.13 Wheel Support & Model Caching

**Date**: Implementation optimization  
**Decision**: Adopt current Python 3.13 compatible wheels (`pandas>=2.2.0`, `numpy>=2.0`) and implement per-user IsolationForest model caching during pipeline execution.  
**Alternatives considered**: Fitting a fresh IsolationForest on every detection day * 61 users (54,000+ repetitive queries).  
**Rationale**:
- Retraining an identical IsolationForest over 60 static baseline days 15 times per user introduced a 15x compute bottleneck with zero change in model weights.
- Caching the fitted IsolationForest per `user_id` reduced full pipeline execution from >15 minutes down to ~40 seconds with 100% mathematical fidelity.
