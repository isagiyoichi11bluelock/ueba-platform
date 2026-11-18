# UEBA Platform — Privacy Design

## Purpose

This document describes how the UEBA Platform protects the privacy of monitored individuals while still enabling effective insider-threat detection.  Privacy is not an afterthought — it is a first-class design constraint.

---

## Principle of Proportionality

The platform collects and analyses only the minimum data necessary to identify anomalous behavioural patterns.  It does **not** monitor:
- Email or message content
- Personal devices or personal accounts
- Physical location via GPS or badge readers (geography is inferred from login IP only)
- Off-system activity of any kind

All monitoring is limited to activity performed on corporate-owned systems within the scope of employment.

---

## Pseudonymisation

Every user is assigned a stable pseudonym (e.g. `U-0042`) generated via HMAC-SHA256 keyed on a random salt stored in the environment (`.env`).  Analyst-facing views, alert queues, timelines, and audit logs all display pseudonyms only.

**Properties of the pseudonymisation scheme:**
- **Stability**: The same user always receives the same pseudonym (enabling cross-event correlation)
- **Unlinkability**: Without the salt, pseudonyms cannot be mapped back to real identities
- **Non-reversibility without salt**: The salt is treated as a secret; compromise requires both the database and the `.env` file

The salt should be rotated periodically.  After rotation, historical pseudonyms must be re-computed (migration script provided separately).

---

## IP Address Truncation

Raw IP addresses are truncated before storage:
- **IPv4**: Last octet zeroed (e.g. `192.168.1.47` → `192.168.1.0`)
- **IPv6**: Truncated to /48 prefix

This retains enough geographic signal for impossible-travel detection while preventing individual host tracking.

---

## Identity Resolution (Break-Glass)

Resolving a pseudonym to a real identity is a privileged, audited action:

1. Only users with role `senior_analyst` may call `resolve_identity()`
2. The caller must supply a written justification of at least 20 characters
3. Every successful resolution is immediately written to the immutable audit log with the actor, timestamp, pseudonym resolved, and justification text
4. Failed resolution attempts (wrong role, insufficient justification) are also logged

The identity map (`user_id → real name`) is never stored in the database.  It exists only in memory during the resolution call, sourced from the pseudonymisation function run in reverse (using the salt).

---

## Audit Trail

The audit log (`audit_log` table) is:
- **Append-only**: No UPDATE or DELETE operations are permitted on this table
- **Chained**: Each record includes a SHA-256 checksum of its content concatenated with the previous record's checksum, forming a tamper-evident chain
- **Comprehensive**: Records identity resolutions, alert status changes, feedback submissions, model retraining events, and configuration changes
- **Retained for 730 days** per the retention policy in `config.yaml`

The chain integrity can be verified at any time via the Audit Log dashboard page.

---

## Data Retention

| Data Type | Retention Period | Rationale |
|-----------|-----------------|-----------|
| Raw events | 90 days | Sufficient for 60-day rolling baseline + 15 days detection |
| Alerts | 365 days | Annual review cycles; regulatory expectation |
| Audit log | 730 days | Two-year forensic lookback |
| Feedback records | 30 days (active) | Prevents stale analyst judgements distorting future scores |

Automated purge jobs (not yet implemented in demo) should run nightly.

---

## Role-Based Access

| Role | Capabilities |
|------|-------------|
| `analyst` | View alerts, timelines, baselines; submit feedback; view audit log by reference |
| `senior_analyst` | All analyst capabilities + identity resolution (with audit) |
| `admin` | Configuration management; cannot view individual alerts |

Dashboard role is controlled via the `DASHBOARD_ROLE` environment variable.

---

## Limitations and Risks

- The pseudonym salt stored in `.env` is a single point of compromise.  In production, use a hardware security module (HSM) or secrets manager.
- The platform does not implement differential privacy.  Aggregate statistics over small groups may still leak individual information.
- Impossible-travel detection relies on IP-to-geography mapping, which can be inaccurate for VPNs and proxies.  VPN-detected IPs should be flagged as `uncertain_geography` rather than treated as ground truth.
- This is a **demonstration system**.  It has not been subject to a formal privacy impact assessment (PIA) or penetration test.  It must not be used to monitor real individuals without appropriate legal basis, notice, and governance.

---

## Legal Basis (Template)

> *In a production deployment, this section should identify the legal basis for processing (e.g. legitimate interest under GDPR Article 6(1)(f)), the data controller, the DPO contact, and links to employee privacy notices.*

---

## References

- GDPR Article 6(1)(f) — Legitimate interests
- GDPR Article 25 — Data protection by design and by default
- ISO/IEC 27001:2022 — Information security management
- NIST SP 800-53 Rev 5 — AU (Audit and Accountability) control family
