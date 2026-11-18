"""
4_User_Timeline.py - Granular timeline, activity maps, and behavioral trend analysis.
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
)

render_role_selector()

render_header(
    title="📈 User Behavioral Timeline & Telemetry",
    subtitle="Holistic Longitudinal Profiling across Logins, Downloads, and Privilege Grants",
    help_text="""
    **User Timeline Telemetry:**
    - Select any pseudonymous identity to examine their 90-day activity profile.
    - **Hour-of-Day Distribution**: Identifies off-hours access deviations.
    - **Download Volume Timeline**: Compares daily egress volumes against the normal baseline band.
    - **Geographic Login Scatter**: Highlights authentication events originating outside habitual territories.
    """,
)

conn = get_db_connection()

users_df = pd.read_sql_query(
    "SELECT user_id, pseudonym, role, department, home_country, home_city, work_start_hour, work_end_hour FROM users ORDER BY pseudonym ASC",
    conn,
)

if users_df.empty:
    st.warning("No user profiles found in database.")
    conn.close()
    st.stop()

user_map = {f"{r['pseudonym']} ({r['role']}, {r['department']})": r["user_id"] for _, r in users_df.iterrows()}
sel_label = st.selectbox("Select Pseudonymous Identity", options=list(user_map.keys()), index=0)
sel_user_id = user_map[sel_label]
user_info = users_df[users_df["user_id"] == sel_user_id].iloc[0]

u_col1, u_col2, u_col3 = st.columns(3)
with u_col1:
    st.markdown(f"**Pseudonym:** `{user_info['pseudonym']}`")
    st.markdown(f"**Role:** {user_info['role']}")
with u_col2:
    st.markdown(f"**Department:** {user_info['department']}")
    st.markdown(f"**Home Base:** {user_info['home_city']}, {user_info['home_country']}")
with u_col3:
    st.markdown(f"**Typical Shift:** {user_info['work_start_hour']:02d}:00 – {user_info['work_end_hour']:02d}:00")

st.divider()

# Load telemetry
logins_df = pd.read_sql_query(
    "SELECT timestamp, country, city, auth_result, device_id FROM login_events WHERE user_id = ? ORDER BY timestamp ASC",
    conn,
    params=(sel_user_id,),
)

downloads_df = pd.read_sql_query(
    "SELECT timestamp, bytes, file_count, destination_type FROM download_events WHERE user_id = ? ORDER BY timestamp ASC",
    conn,
    params=(sel_user_id,),
)

privs_df = pd.read_sql_query(
    "SELECT timestamp, action, target, result FROM privilege_events WHERE user_id = ? ORDER BY timestamp ASC",
    conn,
    params=(sel_user_id,),
)

conn.close()

# --- Visualizations ---
tab1, tab2, tab3 = st.tabs(["🕒 Working Hours & Heatmap", "📦 Download Volumes", "🛡️ Privilege Events"])

with tab1:
    st.markdown("#### Authentication Hour-of-Day Distribution")
    if not logins_df.empty:
        logins_df["hour"] = pd.to_datetime(logins_df["timestamp"]).dt.hour
        hour_counts = logins_df["hour"].value_counts().reindex(range(24), fill_value=0).reset_index()
        hour_counts.columns = ["Hour", "Logins"]
        
        fig_hours = px.bar(
            hour_counts,
            x="Hour",
            y="Logins",
            labels={"Hour": "Hour of Day (UTC)", "Logins": "Login Count"},
            color="Logins",
            color_continuous_scale="Blues",
        )
        # Highlight typical shift
        fig_hours.add_vrect(
            x0=user_info["work_start_hour"] - 0.5,
            x1=user_info["work_end_hour"] + 0.5,
            fillcolor="rgba(46, 204, 113, 0.2)",
            layer="below",
            line_width=0,
            annotation_text="Learned Working Window",
            annotation_position="top left",
        )
        fig_hours.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_hours, use_container_width=True)
    else:
        st.caption("No login events recorded for this user.")

with tab2:
    st.markdown("#### Daily Download Volume Telemetry")
    if not downloads_df.empty:
        downloads_df["date"] = pd.to_datetime(downloads_df["timestamp"]).dt.date
        daily_dl = downloads_df.groupby("date")["bytes"].sum().reset_index()
        daily_dl["mb"] = (daily_dl["bytes"] / (1024 * 1024)).round(2)
        
        fig_dl = px.line(
            daily_dl,
            x="date",
            y="mb",
            markers=True,
            labels={"date": "Date", "mb": "Megabytes Downloaded"},
            title="Total Daily Data Egress (MB)",
        )
        fig_dl.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_dl, use_container_width=True)
    else:
        st.caption("No download events recorded for this user.")

with tab3:
    st.markdown("#### Privileged System & IAM Invocations")
    if not privs_df.empty:
        st.dataframe(
            privs_df,
            column_config={
                "timestamp": "Timestamp (UTC)",
                "action": "Action",
                "target": "Target Asset",
                "result": "Result",
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No privileged operations recorded for this user.")
