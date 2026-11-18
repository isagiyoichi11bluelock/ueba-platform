"""
2_Alert_Queue.py - Filterable and sortable alert triage queue.
"""
from __future__ import annotations

import json
import sqlite3
import pandas as pd
import streamlit as st

from app.components import (
    get_db_connection,
    render_header,
    render_role_selector,
    risk_badge_html,
    SEVERITY_COLORS,
)

render_role_selector()

render_header(
    title="📋 SOC Alert Triage Queue",
    subtitle="Filterable Behavioral Incidents Requiring Analyst Investigation",
    help_text="""
    **Triage Queue Guidelines:**
    - Filter alerts by severity band, review status, employee role, or triggering indicator.
    - An anomaly is **not** proof of malice. Context dampening has already reduced scores for known travel or scheduled on-call shifts.
    - Click **Inspect Alert** to navigate directly to the evidence and decision workflow.
    """,
)

conn = get_db_connection()

try:
    alerts_df = pd.read_sql_query(
        """SELECT a.alert_id, a.user_id, a.pseudonym_id, a.alert_date, a.risk_score,
                  a.severity_band, a.indicators_json, a.context_applied_json, a.summary,
                  a.baseline_confidence, a.status, a.scenario_id, u.role, u.department
           FROM alerts a
           LEFT JOIN users u ON a.user_id = u.user_id
           ORDER BY a.risk_score DESC""",
        conn,
    )
except Exception as e:
    st.error(f"Error loading alerts: {e}")
    st.stop()
finally:
    conn.close()

if alerts_df.empty:
    st.info("No alerts found in database. Please run the pipeline.")
    st.stop()

# --- Sidebar Filters ---
st.sidebar.markdown("### 🔍 Queue Filters")

all_severities = ["critical", "high", "medium", "low"]
sel_severity = st.sidebar.multiselect("Severity Band", options=all_severities, default=["critical", "high", "medium"])

all_statuses = list(alerts_df["status"].unique())
sel_status = st.sidebar.multiselect("Review Status", options=all_statuses, default=all_statuses)

all_roles = sorted([r for r in alerts_df["role"].dropna().unique()])
sel_roles = st.sidebar.multiselect("Role", options=all_roles, default=all_roles)

min_score, max_score = st.sidebar.slider(
    "Score Range", min_value=0.0, max_value=100.0, value=(20.0, 100.0), step=1.0
)

# Apply filters
filtered_df = alerts_df[
    (alerts_df["severity_band"].isin(sel_severity))
    & (alerts_df["status"].isin(sel_status))
    & (alerts_df["role"].isin(sel_roles))
    & (alerts_df["risk_score"] >= min_score)
    & (alerts_df["risk_score"] <= max_score)
]

st.markdown(f"**Showing {len(filtered_df)} of {len(alerts_df)} Total Alerts**")

# Display table
for idx, row in filtered_df.iterrows():
    # Parse top 2 reasons
    reasons = []
    has_context = False
    try:
        inds = json.loads(row["indicators_json"])
        for item in inds:
            if item.get("name") and item["name"] != "CHAIN_BONUS":
                pts = item.get("severity_points", 0)
                reasons.append(f"{item['name']} (+{pts:.0f} pts)")
    except Exception:
        pass

    try:
        ctxs = json.loads(row["context_applied_json"])
        if ctxs:
            has_context = True
    except Exception:
        pass

    top_reasons_str = " • ".join(reasons[:2]) if reasons else "Composite behavioral deviation"
    context_badge = " 🏷️ *Context Applied*" if has_context else ""

    with st.container():
        c_badge, c_info, c_status, c_act = st.columns([1.5, 4.5, 1.5, 1.5])
        
        with c_badge:
            st.markdown(risk_badge_html(row["risk_score"], row["severity_band"]), unsafe_allow_html=True)
            st.caption(f"📅 {row['alert_date']}")

        with c_info:
            st.markdown(f"**{row['pseudonym_id']}** ({row['role'] or 'Unknown'}) {context_badge}")
            st.markdown(f"<span style='font-size: 0.85rem; color: #555;'>{top_reasons_str}</span>", unsafe_allow_html=True)

        with c_status:
            status_color = "#27ae60" if row["status"] != "open" else "#e67e22"
            st.markdown(f"<span style='color: {status_color}; font-weight: 600;'>{row['status'].upper()}</span>", unsafe_allow_html=True)
            st.caption(f"Confidence: {int(row['baseline_confidence']*100)}%")

        with c_act:
            if st.button("Inspect Alert 🔍", key=f"btn_{row['alert_id']}"):
                st.session_state["selected_alert_id"] = row["alert_id"]
                st.switch_page("pages/3_Alert_Detail.py")

        st.divider()
