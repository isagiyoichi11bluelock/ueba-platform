"""
1_Overview.py - Executive SOC posture, KPIs, and risk distribution.
"""
from __future__ import annotations

import json
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app_legacy.components import (
    get_db_connection,
    render_header,
    render_role_selector,
    SEVERITY_COLORS,
)

render_role_selector()

render_header(
    title="📊 SOC Risk Posture & Overview",
    subtitle="Aggregate Behavioral Health, Anomaly Distribution, and Departmental Heatmap",
    help_text="""
    **Executive SOC Overview:**
    - **KPIs**: Summary of active threat signals, severity breakdown, and review cadence.
    - **Risk Score Distribution**: Highlights the separation between benign background noise and high-confidence alerts.
    - **Top Indicators**: Most frequently triggered behavioral deviations across the workforce.
    - **Department Risk Heatmap**: Departmental activity aggregation strictly on pseudonymous identifiers.
    """,
)

conn = get_db_connection()

try:
    alerts_df = pd.read_sql_query("SELECT * FROM alerts", conn)
    users_df = pd.read_sql_query("SELECT user_id, pseudonym, role, department FROM users", conn)
    feedback_df = pd.read_sql_query("SELECT * FROM analyst_feedback", conn)
except Exception as e:
    st.error(f"Error loading analytics data: {e}")
    st.stop()
finally:
    conn.close()

if alerts_df.empty:
    st.warning("No alerts generated yet. Please run the data generation and pipeline script.")
    st.stop()

# Merge user metadata
merged_alerts = alerts_df.merge(users_df, on="user_id", how="left")

# --- Top KPIs ---
total_alerts = len(alerts_df)
crit_count = len(alerts_df[alerts_df["severity_band"] == "critical"])
high_count = len(alerts_df[alerts_df["severity_band"] == "high"])
med_count = len(alerts_df[alerts_df["severity_band"] == "medium"])
low_count = len(alerts_df[alerts_df["severity_band"] == "low"])
reviewed_count = len(alerts_df[alerts_df["status"] != "open"])

pct_benign = 0.0
if not feedback_df.empty:
    benign_cnt = len(feedback_df[feedback_df["verdict"].isin(["benign_expected", "false_positive"])])
    pct_benign = round(100.0 * benign_cnt / len(feedback_df), 1)

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("Total Alerts", f"{total_alerts}")
kpi2.metric("Critical / High", f"{crit_count + high_count}", delta=f"{crit_count} Critical", delta_color="inverse")
kpi3.metric("Medium / Low", f"{med_count + low_count}")
kpi4.metric("Review Progress", f"{reviewed_count}/{total_alerts}", delta=f"{round(100*reviewed_count/max(total_alerts,1),1)}%")
kpi5.metric("Benign Verdict Rate", f"{pct_benign}%")

st.markdown("<br>", unsafe_allow_html=True)

# --- Charts Row 1 ---
row1_col1, row1_col2 = st.columns([1, 1])

with row1_col1:
    st.markdown("#### 📈 Risk Score Distribution")
    fig_hist = px.histogram(
        alerts_df,
        x="risk_score",
        nbins=20,
        color="severity_band",
        color_discrete_map=SEVERITY_COLORS,
        labels={"risk_score": "Composite Risk Score (0–100)", "count": "Alert Count"},
    )
    fig_hist.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_hist, use_container_width=True)

with row1_col2:
    st.markdown("#### 📅 Alert Volume Over Time")
    alerts_by_date = (
        alerts_df.groupby(["alert_date", "severity_band"])
        .size()
        .reset_index(name="count")
    )
    fig_time = px.bar(
        alerts_by_date,
        x="alert_date",
        y="count",
        color="severity_band",
        color_discrete_map=SEVERITY_COLORS,
        labels={"alert_date": "Evaluation Date", "count": "Alerts"},
    )
    fig_time.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_time, use_container_width=True)

# --- Charts Row 2 ---
row2_col1, row2_col2 = st.columns([1, 1])

with row2_col1:
    st.markdown("#### 🏷️ Top Triggered Indicators")
    indicator_counts = {}
    for raw in alerts_df["indicators_json"]:
        try:
            inds = json.loads(raw)
            for item in inds:
                name = item.get("name")
                if name and name != "CHAIN_BONUS":
                    indicator_counts[name] = indicator_counts.get(name, 0) + 1
        except Exception:
            pass
    
    ind_df = (
        pd.DataFrame(list(indicator_counts.items()), columns=["Indicator", "Count"])
        .sort_values(by="Count", ascending=True)
        .tail(8)
    )
    fig_ind = px.bar(
        ind_df,
        x="Count",
        y="Indicator",
        orientation="h",
        color_discrete_sequence=["#3498DB"],
    )
    fig_ind.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_ind, use_container_width=True)

with row2_col2:
    st.markdown("#### 🏢 Departmental Risk Heatmap")
    dept_risk = (
        merged_alerts.groupby("department")["risk_score"]
        .agg(["count", "mean", "max"])
        .reset_index()
    )
    dept_risk["mean"] = dept_risk["mean"].round(1)
    dept_risk["max"] = dept_risk["max"].round(1)
    dept_risk.columns = ["Department", "Alert Count", "Mean Risk Score", "Max Risk Score"]
    
    fig_heatmap = px.scatter(
        dept_risk,
        x="Department",
        y="Mean Risk Score",
        size="Alert Count",
        color="Max Risk Score",
        color_continuous_scale="Reds",
        size_max=40,
    )
    fig_heatmap.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_heatmap, use_container_width=True)
