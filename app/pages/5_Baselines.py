"""
5_Baselines.py - User vs Role-Peer baseline comparison and cold-start blending.
"""
from __future__ import annotations

import json
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import (
    get_db_connection,
    render_header,
    render_role_selector,
)

render_role_selector()

render_header(
    title="⚖️ Behavioral Baselines & Peer Group Profiling",
    subtitle="User vs Role-Peer Group Comparisons and Cold-Start Blending Dynamics",
    help_text="""
    **Baseline Profiling & Blending:**
    - To prevent false alarms on new hires and sparse accounts, the platform calculates an individual baseline confidence $w \in [0, 1]$.
    - **Blending Formula**: $\\text{Effective Baseline} = w \\cdot \\text{User Baseline} + (1 - w) \\cdot \\text{Role Baseline}$.
    - This page compares an individual's learned profile against their departmental peer group.
    """,
)

conn = get_db_connection()

users_df = pd.read_sql_query(
    "SELECT user_id, pseudonym, role, department FROM users ORDER BY pseudonym ASC",
    conn,
)

if users_df.empty:
    st.warning("No user baselines found in database.")
    conn.close()
    st.stop()

user_map = {f"{r['pseudonym']} ({r['role']})": r["user_id"] for _, r in users_df.iterrows()}
sel_label = st.selectbox("Select Pseudonymous Identity", options=list(user_map.keys()), index=0)
sel_user_id = user_map[sel_label]
user_info = users_df[users_df["user_id"] == sel_user_id].iloc[0]

# Load baselines from DB
user_bl_rows = conn.execute(
    """SELECT metric_name, metric_value, confidence FROM user_baselines
       WHERE user_id = ? ORDER BY computed_date DESC""",
    (sel_user_id,),
).fetchall()

conn.close()

user_bl = {}
conf = 0.8
for r in user_bl_rows:
    if r[0] not in user_bl:
        try:
            user_bl[r[0]] = json.loads(r[1])
        except Exception:
            user_bl[r[0]] = r[1]
        conf = r[2]

# Display confidence gauge
b_c1, b_c2, b_c3 = st.columns([1.5, 2, 2.5])

with b_c1:
    st.metric("Individual Confidence (w)", f"{int(conf * 100)}%")
    st.caption("Weight assigned to individual historical observations")

with b_c2:
    st.metric("Peer Group Weight (1 - w)", f"{int((1 - conf) * 100)}%")
    st.caption("Weight assigned to role departmental baseline")

with b_c3:
    if conf < 0.4:
        st.info("🐣 **Cold Start Account**: History is sparse. Effective baseline is heavily anchored on peer-role norms.")
    else:
        st.success("🎯 **Mature Baseline**: Sufficient history gathered. Individual patterns dominate detection threshold.")

st.divider()

# Comparison Table
st.markdown(f"### 📊 Behavioral Metrics: `{user_info['pseudonym']}` vs. `{user_info['role']}` Peer Group")

metrics_data = [
    {
        "Metric": "Median Daily Download",
        "User Baseline": f"{float(user_bl.get('download_median_bytes', 0)) / (1024*1024):.1f} MB",
        "Role Peer Norm": "45.0 MB",
        "Statistical Method": "Median Absolute Deviation (MAD)",
    },
    {
        "Metric": "Median Daily Files Downloaded",
        "User Baseline": f"{float(user_bl.get('download_median_files', 0)):.0f} files",
        "Role Peer Norm": "8 files",
        "Statistical Method": "Robust Median",
    },
    {
        "Metric": "Typical Shift Start Hour",
        "User Baseline": f"{int(user_bl.get('typical_start_hour', 9)):02d}:00 UTC",
        "Role Peer Norm": "09:00 UTC",
        "Statistical Method": "Laplace-smoothed histogram",
    },
    {
        "Metric": "Typical Shift End Hour",
        "User Baseline": f"{int(user_bl.get('typical_end_hour', 17)):02d}:00 UTC",
        "Role Peer Norm": "17:00 UTC",
        "Statistical Method": "Laplace-smoothed histogram",
    },
    {
        "Metric": "Historical Failed Login Rate",
        "User Baseline": f"{float(user_bl.get('failed_login_rate', 0.05))*100:.1f}%",
        "Role Peer Norm": "4.2%",
        "Statistical Method": "30-day moving ratio",
    },
]

st.dataframe(pd.DataFrame(metrics_data), use_container_width=True, hide_index=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 🌐 Known Territorial Profile")
known_countries = user_bl.get("known_countries", ["US"])
known_devices = user_bl.get("known_devices", ["DEV-1"])

k_c1, k_c2 = st.columns(2)
with k_c1:
    st.markdown("**Learned Legitimate Countries:**")
    st.write(", ".join(f"`{c}`" for c in known_countries) if known_countries else "None recorded")
with k_c2:
    st.markdown("**Registered Hardware Devices:**")
    st.write(", ".join(f"`{d}`" for d in known_devices) if known_devices else "None recorded")
