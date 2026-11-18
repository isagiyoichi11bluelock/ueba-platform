"""
3_Alert_Detail.py - The Hero View: Deep Incident Investigation & Explainability.
"""
from __future__ import annotations

import json
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    get_db_connection,
    render_header,
    render_role_selector,
    risk_badge_html,
    score_gauge,
    waterfall_score_chart,
)
from src.ueba.audit import log_audit_event
from src.ueba.feedback import submit_feedback
from src.ueba.privacy import request_reidentification

current_role = render_role_selector()

render_header(
    title="🔍 Incident Deep Dive & Explainability",
    subtitle="Full Evidence Provenance, Context Adjustments, and Defensible Analyst Workflow",
    help_text="""
    **The Hero Page — How to Investigate:**
    - **Score Breakdown**: Interactive composition chart showing exactly which indicators drove the risk score.
    - **Explainable Cards**: Transparent cards detailing observed values, normal baselines, and why each anomaly matters.
    - **Event Timeline**: Chronological Plotly visualization highlighting triggering events.
    - **Analyst Actions**: Record defensible verdicts (`confirmed_suspicious`, `benign_expected`, etc.). Marking an alert benign can auto-generate a 30-day adjustment rule.
    - **Gated Re-Identification**: Senior analysts can unmask the internal employee ID with mandatory audited justification.
    """,
)

conn = get_db_connection()

# Determine selected alert
alert_id = st.session_state.get("selected_alert_id")

all_alerts = conn.execute(
    """SELECT a.alert_id, a.pseudonym_id, a.alert_date, a.risk_score, a.severity_band, u.role
       FROM alerts a LEFT JOIN users u ON a.user_id = u.user_id
       ORDER BY a.risk_score DESC"""
).fetchall()

if not all_alerts:
    st.warning("No alerts available to display.")
    conn.close()
    st.stop()

alert_options = {
    f"{r[1]} — {r[2]} — Risk {int(r[3])} ({r[4].upper()}) [{r[5] or 'Role'}]": r[0]
    for r in all_alerts
}

# If no selection or selected not in list, pick top alert
if not alert_id or alert_id not in [r[0] for r in all_alerts]:
    alert_id = all_alerts[0][0]
    st.session_state["selected_alert_id"] = alert_id

# Find current index for selectbox
curr_label = [k for k, v in alert_options.items() if v == alert_id]
default_idx = list(alert_options.keys()).index(curr_label[0]) if curr_label else 0

sel_label = st.selectbox("Select Alert to Investigate", options=list(alert_options.keys()), index=default_idx)
alert_id = alert_options[sel_label]
st.session_state["selected_alert_id"] = alert_id

# Fetch full alert details
alert_row = conn.execute(
    """SELECT a.*, u.role, u.department, u.home_country, u.home_city,
              u.work_start_hour, u.work_end_hour, u.is_contractor, u.is_night_shift
       FROM alerts a
       LEFT JOIN users u ON a.user_id = u.user_id
       WHERE a.alert_id = ?""",
    (alert_id,),
).fetchone()

if not alert_row:
    st.error("Alert not found.")
    conn.close()
    st.stop()

# Parse JSON payloads
indicators = []
try:
    indicators = json.loads(alert_row["indicators_json"])
except Exception:
    pass

contexts_applied = []
try:
    contexts_applied = json.loads(alert_row["context_applied_json"])
except Exception:
    pass

st.markdown("<br>", unsafe_allow_html=True)

# --- Alert Header Row ---
head_col1, head_col2, head_col3 = st.columns([2, 1.5, 1.5])

with head_col1:
    st.markdown(f"## 👤 {alert_row['pseudonym_id']}")
    shift_tag = " • 🌙 Night Shift" if alert_row["is_night_shift"] else ""
    contractor_tag = " • 🏢 Contractor" if alert_row["is_contractor"] else ""
    st.markdown(
        f"**Role:** {alert_row['role']} ({alert_row['department']}){shift_tag}{contractor_tag}  \n"
        f"**Location:** {alert_row['home_city']}, {alert_row['home_country']}  \n"
        f"**Incident Date:** {alert_row['alert_date']}"
    )

with head_col2:
    st.plotly_chart(score_gauge(alert_row["risk_score"], alert_row["severity_band"]), use_container_width=True)

with head_col3:
    st.markdown("### Status & Confidence")
    st.markdown(f"**Current Status:** `{alert_row['status'].upper()}`")
    st.markdown(f"**Baseline Confidence:** `{int(alert_row['baseline_confidence'] * 100)}%`")
    if alert_row["scenario_id"]:
        st.markdown(f"**Injected Scenario:** `{alert_row['scenario_id']}`")

st.info(f"**Automated Synthesis:** {alert_row['summary']}", icon="💡")

# --- Context Applied Banner (if any) ---
if contexts_applied:
    st.success(
        f"🛡️ **Business Context Applied:** This incident was recognized as having legitimate operational justification "
        f"({', '.join(c.get('context_type', 'Context') for c in contexts_applied)}). "
        f"Indicator severity was dampened, preventing unnecessary escalation while preserving auditability.",
        icon="✅",
    )

# --- Visual Score Composition ---
st.markdown("### 📊 Score Composition & Waterfall")
st.plotly_chart(waterfall_score_chart(indicators, alert_row["risk_score"]), use_container_width=True)

# --- Explainable Indicator Cards ---
st.markdown("### 🧩 Behavioral Indicators (Evidence Breakdown)")

evidence_event_ids = []

for ind in indicators:
    if ind.get("name") == "CHAIN_BONUS":
        with st.container():
            st.markdown(
                f"""
                <div style="background-color: #fdf2e9; border-left: 5px solid #e67e22; padding: 12px 16px; border-radius: 6px; margin-bottom: 12px;">
                    <h4 style="margin: 0; color: #d35400;">🔗 Multi-Stage Attack Chain Bonus</h4>
                    <p style="margin: 4px 0 0 0; font-size: 0.95rem; color: #333;">
                        Sequential correlation detected: {', '.join(ind.get('bonuses', []))}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        continue

    ind_name = ind.get("name", "Indicator").replace("_", " ").title()
    pts = ind.get("severity_points", 0)
    conf = int(ind.get("confidence", 1.0) * 100)
    events = ind.get("evidence_event_ids", [])
    evidence_event_ids.extend(events)
    
    damp_info = ""
    if ind.get("context_dampened"):
        orig = ind.get("original_severity_points", pts)
        damp_info = f"<span style='color: #27ae60; font-weight: 600;'> (Dampened from {orig:.1f} pts via {ind.get('dampening_context')})</span>"

    with st.expander(f"⚠️ {ind_name} (+{pts:.1f} pts){' • Context Dampened' if ind.get('context_dampened') else ''}", expanded=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**Observed Value:** `{ind.get('observed_value')}`")
            st.markdown(f"**Learned Baseline:** `{ind.get('baseline_value')}`")
            st.markdown(f"**Why this matters:** {ind.get('why_it_matters')}")
            if damp_info:
                st.markdown(f"**Context Adjustment:** {ind.get('dampening_note', '')}")
        with c2:
            st.metric("Base Severity", f"{pts:.1f} pts")
            st.caption(f"Rule Confidence: {conf}%")
            if events:
                st.markdown(f"**Evidence IDs:**  \n`{', '.join(events)}`")

# --- Event Timeline ---
st.markdown("### 🕒 Triggering Activity Timeline")
user_id = alert_row["user_id"]
alert_date = alert_row["alert_date"]

timeline_query = """
SELECT timestamp, 'Login' as event_type, 
       auth_result || ' (' || country || '/' || city || ') via ' || device_id as description,
       event_id
FROM login_events
WHERE user_id = ? AND date(timestamp) = ?
UNION ALL
SELECT timestamp, 'File Access' as event_type, 
       action || ' on ' || resource_id as description,
       event_id
FROM file_access_events
WHERE user_id = ? AND date(timestamp) = ?
UNION ALL
SELECT timestamp, 'Download' as event_type, 
       bytes / 1048576 || ' MB to ' || destination_type as description,
       event_id
FROM download_events
WHERE user_id = ? AND date(timestamp) = ?
UNION ALL
SELECT timestamp, 'Privilege' as event_type, 
       action || ' on ' || target as description,
       event_id
FROM privilege_events
WHERE user_id = ? AND date(timestamp) = ?
ORDER BY timestamp ASC
"""

events_df = pd.read_sql_query(timeline_query, conn, params=(user_id, alert_date, user_id, alert_date, user_id, alert_date, user_id, alert_date))

if not events_df.empty:
    events_df["is_evidence"] = events_df["event_id"].isin(evidence_event_ids)
    events_df["color"] = events_df["is_evidence"].apply(lambda x: "#e74c3c" if x else "#3498db")
    
    st.dataframe(
        events_df[["timestamp", "event_type", "description", "event_id", "is_evidence"]],
        column_config={
            "timestamp": "Time (UTC)",
            "event_type": "Event Class",
            "description": "Details",
            "event_id": "Audit Event ID",
            "is_evidence": "Direct Trigger Evidence",
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("No granular event logs available for this specific date.")

st.markdown("<br>", unsafe_allow_html=True)

# --- Analyst Actions & Feedback Form ---
st.markdown("### ✍️ Analyst Review & Verdict Submission")
st.caption("🛡️ *An anomaly is not proof of wrongdoing. Document findings objectively.*")

with st.form(key=f"form_review_{alert_id}"):
    f_c1, f_c2 = st.columns([1, 1])
    with f_c1:
        verdict = st.selectbox(
            "Verdict",
            options=["confirmed_suspicious", "benign_expected", "needs_more_info", "false_positive"],
            index=0 if alert_row["status"] == "open" else ["confirmed_suspicious", "benign_expected", "needs_more_info", "false_positive"].index(alert_row["status"]),
            help="Select review finding.",
        )
    with f_c2:
        create_adj = st.checkbox(
            "Create 30-Day Dampening Rule (if Benign Expected)",
            value=False,
            help="Reduces future alert points for this user and dominant indicator for 30 days.",
        )

    comment = st.text_area("Analyst Justification & Notes (max 500 chars)", max_chars=500, placeholder="Explain reason for verdict...")
    submitted = st.form_submit_button("Submit Verdict & Log to Audit Ledger 💾")

    if submitted:
        if current_role == "auditor":
            st.error("Auditor role has read-only permissions and cannot submit alert verdicts.")
        else:
            try:
                top_ind_name = indicators[0]["name"] if indicators else None
                fid = submit_feedback(
                    conn=conn,
                    alert_id=alert_id,
                    analyst=f"{current_role}_user",
                    verdict=verdict,
                    comment=comment,
                    create_adjustment=create_adj,
                    indicator_id=top_ind_name,
                )
                st.success(f"Verdict '{verdict}' successfully recorded and hashed to audit chain! (Feedback ID: {fid[:8]})")
                st.rerun()
            except Exception as ex:
                st.error(f"Error submitting feedback: {ex}")

st.markdown("<br>", unsafe_allow_html=True)

# --- Separation of Duties: Gated Re-identification ---
st.markdown("### 🔐 Separation of Duties: Gated Identity Re-identification")

with st.expander("Request Identity Disclosure (Strictly Controlled)", expanded=False):
    st.warning(
        "⚠️ **Legal & Ethical Notice:** Cleartext employee identity is restricted under GDPR Art. 25 & India DPDP Act. "
        "Re-identification requires the `senior_analyst` role and a mandatory 20+ character justification written to the immutable audit log."
    )
    
    justification = st.text_input("Formal Business Justification", placeholder="e.g. Incident escalation authorized by Chief Information Security Officer for Ticket INC-9812")
    
    if st.button("Unlock Cleartext Employee ID 🔓"):
        if current_role != "senior_analyst":
            st.error(f"Access Denied: Current role '{current_role}' cannot request re-identification. Switch role to 'senior_analyst' in sidebar.")
        elif len(justification.strip()) < 20:
            st.error("Justification too short: Minimum 20 characters required for audit compliance.")
        else:
            try:
                unmasked = request_reidentification(
                    conn=conn,
                    pseudonym=alert_row["pseudonym_id"],
                    requester="senior_analyst_user",
                    requester_role="senior_analyst",
                    justification=justification,
                    audit_fn=log_audit_event,
                )
                st.success(f"Identity Revealed: Internal User ID = **{unmasked['user_id']}**")
                st.caption(unmasked["note"])
            except Exception as ex:
                st.error(f"Re-identification failed: {ex}")

conn.close()
