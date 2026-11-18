# UEBA Platform — 5-Minute Pitch & Demo Script

**Speaker Persona:** Lead Security Engineer & Architect  
**Audience:** Security Leadership, SOC Operations & Architecture Review Panel  
**Total Target Time:** 5 Minutes 00 Seconds  
**Demo Dashboard URL:** `http://localhost:8501`

---

## Pitch Narrative & Timing Breakdown

### [0:00 – 0:45] Act 1: The Insider Threat Crisis & The Broken Status Quo
> *"Good morning, everyone. In 2026, the average cost of an insider data breach exceeds $16 million. Traditional security solutions face a devastating dilemma: either security teams drown in thousands of daily false-positive alerts, or they deploy invasive spyware that monitors employee keystrokes and webcam feeds—destroying trust and violating privacy laws like the EU GDPR and India’s DPDP Act.*
>
> *Worse still, traditional rule engines flag anyone who travels, works late, or changes teams as an 'attacker'. But **an anomaly is not proof of wrongdoing**. Today, we are presenting our User and Entity Behavior Analytics (UEBA) Platform: an explainable, privacy-preserving, context-aware insider threat detection engine."*

---

### [0:45 – 1:30] Act 2: The Core Approach — The "Fair Security Guard" Analogy
> *"Think of our platform like a **fair, well-informed security guard at a corporate headquarters**. 
>
> 1. A bad guard stops everyone entering at 8 PM, accusing them of trespassing.
> 2. A good guard checks the maintenance roster, sees that Alice is on-call tonight, and lets her do her job without sounding the alarm.
> 3. That same guard knows what's normal for Alice personally, what's normal for Alice’s peer group (software engineers), and crucially, checks the company's approved calendar.
>
> Our technical architecture implements this through four synchronized innovations:
> - **Blended Baselines**: Combining individual history with role-peer baselines to solve the 'cold-start' problem for new hires without data leakage.
> - **Diminishing Returns Scoring**: Preventing indicator saturation while rewarding multi-stage anomaly chains.
> - **First-Class Context Dampening**: Lowering risk scores for approved business travel, month-end financial close, or emergency maintenance, while keeping the audit trail transparent.
> - **Privacy by Design**: Cryptographic pseudonymization via HMAC-SHA256, IP truncation to /24, and separation of duties for identity re-identification."*

---

### [1:30 – 2:30] Act 3: Live Demo — S1 Compromised Account Killchain
*(Switch to Streamlit Dashboard → **Scenarios Demo** or **Alert Detail**)*
> *"Let’s look at the live platform. Here on the **Scenarios Demo** page, we have 8 synthetic ground-truth scenarios injected into our 90-day event database. Let’s trigger Scenario 1: Compromised Credentials.
>
> Watch the alert detail:
> - The subject user is represented strictly by pseudonym `U-9E41F2`—no names, emails, or cleartext employee IDs are displayed in the analyst UI.
> - The risk score is **96 (Critical)**.
> - Why? Look at the **Explainable Indicator Cards**:
>   1. `FAILED_LOGIN_BURST_THEN_SUCCESS`: 8 password failures followed immediately by a successful MFA bypass.
>   2. `NEW_COUNTRY` & `UNUSUAL_HOUR`: Session originated from Tokyo at 3:12 AM local time.
>   3. `PRIVILEGE_ESCALATION_SEQUENCE`: Sudo and IAM role grants invoked within minutes.
>   4. `DOWNLOAD_VOLUME_SPIKE` to `external_share`: 2.4 GB of restricted source code exfiltrated.
> - Notice the **Chain Bonus**: because location anomaly, privilege escalation, and exfiltration occurred in sequence, our engine added a chaining multiplier.
> - Every indicator links directly to the specific event IDs (`L-1849`, `PR-0421`, `DL-0891`) giving the SOC analyst instant, irrefutable evidence."*

---

### [2:30 – 3:30] Act 4: The Innovation — S4 Benign Travel vs. S8 Unapproved Contrast
*(Switch to Scenario S4, then S8)*
> *"Now let's examine our biggest competitive differentiator: **benign-exception handling**.
>
> In Scenario 4, a Senior Financial Analyst logs in from London at an unusual hour from a new laptop. In any legacy UEBA tool, this triggers a high-severity incident and wakes up the analyst on shift.
> But look at our alert: the score is dampened down to **28 (Low)**!
> Why? The platform correlated the authentication with an authorized `approved_travel` context record signed off by HR.
>
> Notice what happened:
> - The alert was **not silently deleted**—silent suppression creates compliance blind spots.
> - Instead, the indicator card clearly states: *'Severity reduced 70% due to approved travel context'*.
>
> Now, look at **Scenario 8**. This is our negative control: identical user, identical foreign login, identical odd hours, but **zero travel record in the registry**.
> Result? Risk Score jumps to **68 (High)**.
> This proves conclusively that our engine isn't using blunt heuristics; dampening is dynamically driven by validated business evidence."*

---

### [3:30 – 4:15] Act 5: Analyst Feedback Loop & Cryptographic Audit Chain
*(Switch to **Alert Queue** review modal → **Audit Log** page)*
> *"When an analyst reviews an alert, what happens next?
> 1. An analyst can mark a finding as `benign_expected`.
> 2. This creates an **Adjustment Rule** with an automated 30-day expiration, preventing alert fatigue without permanently blinding the model.
> 3. Now let’s visit the **Audit Log** page. Every single analyst verdict, rule modification, pipeline run, and gated identity re-identification is cryptographically chained using SHA-256 hashes (`Hash_n = SHA256(Hash_{n-1} + Entry)`).
> 
> Let's click **'Verify Audit Integrity'**. The engine recomputes the entire blockchain-style ledger across all entries: **PASS - 100% Integrity**. If an insider or compromised administrator alters a single character in the SQLite database, the chain breaks immediately and flags the exact corrupted entry."*

---

### [4:15 – 4:45] Act 6: Privacy by Design & Honest Limitations
*(Switch to **Privacy and Limitations** page)*
> *"We built this platform adhering to the strictest interpretation of India’s Digital Personal Data Protection (DPDP) Act and the GDPR:
> - **Data Minimization**: Raw IPs are truncated to `/24`. Free-text chat or surveillance captures are banned from ingestion.
> - **Separation of Duties**: Only a `senior_analyst` with a logged, audited justification of at least 20 characters can view an employee's internal ID.
> - **Transparent Limitations**: We document our technical boundary honestly: our Isolation Forest is strictly an auxiliary signal (capped at 15 points); our thresholds are tuned for structured audit events; and we acknowledge that a slow-boiling, patient insider requires long-horizon baseline memory."*

---

### [4:45 – 5:00] Act 7: Scalability & Closing
> *"Under the hood, everything runs locally on standard Python without paid APIs or external dependencies. In enterprise production, the architecture seamlessly migrates from SQLite to ClickHouse or PostgreSQL with Apache Kafka event streaming and OpenSearch SIEM integration.
>
> In summary: high detection accuracy, zero black-box obscurity, mathematical audit protection, and respect for employee privacy. Thank you, and we welcome your questions!"*

---

## Anticipated Judge Q&A (Preparation & Defense)

### Q1: *"Why use rule-based indicators instead of an end-to-end Deep Learning or Graph Neural Network model?"*
**Answer:**  
*"In cybersecurity operations and labor compliance, black-box neural networks fail two non-negotiable requirements: legal defensibility and analyst actionability. If an ML model flags an employee with an arbitrary embedding distance, HR cannot confront the employee, and legal teams cannot present the evidence to a judge or works council. Furthermore, deep learning models are notoriously vulnerable to baseline poisoning where an insider slowly trains the model to accept malicious behavior as normal. Our rule-first, ML-supporting design guarantees deterministic explainability down to the exact event ID while using Isolation Forest as a secondary cross-check."*

---

### Q2: *"How do you prevent insiders from abusing the Context Dampening feature by submitting fake travel requests?"*
**Answer:**  
*"Great question. We implement three distinct layers of protection:
1. **Separation of Authorization**: Context events cannot be created by the user; they must originate from verified business systems (e.g., HRIS, ERP, PagerDuty) with authenticated approver metadata (`approved_by_role`).
2. **Undampenable Indicators**: Indicators like `IMPOSSIBLE_TRAVEL` (>900 km/h) and `FAILED_LOGIN_BURST_THEN_SUCCESS` are hardcoded in `config.yaml` as immune to dampening. Even with a valid travel request, brute-forcing passwords or teleporting across continents cannot be dampened.
3. **Reduction Caps**: The maximum reduction factor is capped at 80% (configurable), ensuring that extreme, destructive behavior (such as mass deletion) still breaches the medium/high threshold."*

---

### Q3: *"How does the platform handle the cold-start problem when a new employee joins?"*
**Answer:**  
*"This is Scenario S6 in our test suite. For employees with fewer than 30 days of history, individual baselines lack statistical confidence. We calculate a sample confidence weight $w \in [0, 1]$ based on days of history and event count. The effective baseline is mathematically blended:  
$$\text{Baseline}_{\text{effective}} = w \cdot \text{Baseline}_{\text{user}} + (1 - w) \cdot \text{Baseline}_{\text{peer\_role}}$$  
For a new hire with 5 days ($w \approx 0.17$), their actions are evaluated 83% against their role peers (e.g., typical developer file counts and hours), preventing false positives while maintaining baseline coverage from Day 1."*

---

### Q4: *"Why robust statistics (Median/MAD) instead of Mean and Standard Deviation?"*
**Answer:**  
*"Normal Gaussian statistics (mean and standard deviation) are easily poisoned by extreme outliers. If an insider downloads 5 GB on one day, a standard mean shoots up, artificially inflating the standard deviation and blinding the system to subsequent 2 GB downloads. The Median and Median Absolute Deviation (MAD) have a 50% breakdown point—meaning half of the observations can be corrupted without skewing the baseline central tendency."*

---

### Q5: *"Can this architecture scale to an enterprise with 50,000 employees?"*
**Answer:**  
*"Yes. Our pipeline logic is stateless per user-day. In an enterprise deployment:
1. SQLite is swapped for a distributed analytical columnar database like ClickHouse or Amazon Redshift.
2. Ingest occurs via Apache Kafka or AWS Kinesis event streams into Redis/Feast feature stores.
3. Baseline computation runs as a nightly Apache Spark or Dataproc batch job.
4. Alerts push directly to existing SOC SIEM platforms (Splunk, Microsoft Sentinel, or Google SecOps) via standard CEF/Syslog or webhooks."*

