"""
6_Scenarios_Demo.py - Live interactive demonstration of S1–S8 test scenarios.
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
)

render_role_selector()

render_header(
    title="🎯 Scenario Demonstrations (S1–S8 Ground Truth)",
    subtitle="Live Interactive Validation of Injected Threats and Context-Dampened Exceptions",
    help_text="""
    **The Pitch Core Page:**
    - Test the platform's behavior against 8 ground-truth scenarios injected into the 90-day event database.
    - Demonstrates high recall on malicious scenarios (**S1, S2, S3, S8**) while proving low false positives on benign scenarios (**S4, S5, S6, S7**).
    - Notice the dramatic score separation between **S4** (approved travel, Low Risk) and **S8** (unapproved travel, High Risk).
    """,
)

conn = get_db_connection()

try:
    gt_df = pd.read_sql_query("SELECT * FROM ground_truth ORDER BY scenario_id ASC", conn)
except Exception as e:
    st.error(f"Error loading ground truth: {e}")
    conn.close()
    st.stop()

if gt_df.empty:
    st.warning("No ground truth records found in database. Run build_dataset.py first.")
    conn.close()
    st.stop()

# Helper to query score for a scenario
def get_scenario_result(scenario_row):
    s_id = scenario_row["scenario_id"]
    u_id = scenario_row["user_id"]
    s_time = scenario_row["start_time"][:10]
    e_time = scenario_row["end_time"][:10]
    exp_min = scenario_row["expected_min_score"]
    exp_max = scenario_row["expected_max_score"]
    
    # Query best alert
    alert = conn.execute(
        """SELECT alert_id, risk_score, severity_band, indicators_json, context_applied_json, summary
           FROM alerts
           WHERE user_id = ? AND alert_date >= ? AND alert_date <= ?
           ORDER BY risk_score DESC LIMIT 1""",
        (u_id, s_time, e_time),
    ).fetchone()

    score = alert[1] if alert else 0.0
    band = alert[2] if alert else "none"
    alert_id = alert[0] if alert else None
    passed = exp_min <= score <= exp_max

    return {
        "scenario_id": s_id,
        "name": scenario_row["description"].split(":")[0] if ":" in scenario_row["description"] else s_id,
        "type": "Malicious" if scenario_row["label"] == "malicious_or_compromised" else "Benign Exception",
        "expected": f"[{int(exp_min)}, {int(exp_max)}]",
        "actual_score": score,
        "severity_band": band,
        "passed": passed,
        "alert_id": alert_id,
        "description": scenario_row["description"],
    }

# Compute all results
all_results = [get_scenario_result(row) for _, row in gt_df.iterrows()]

# --- Run All Scenarios Banner ---
st.markdown("### 🚀 One-Click Global Validation")

col_btn, col_stats = st.columns([1.5, 3.5])

with col_btn:
    if st.button("▶️ Run & Verify All Scenarios", use_container_width=True):
        st.session_state["ran_all_scenarios"] = True

passed_count = sum(1 for r in all_results if r["passed"])
total_scenarios = len(all_results)

with col_stats:
    if passed_count == total_scenarios:
        st.success(f"✅ **ALL {total_scenarios} SCENARIOS PASSED:** Every outcome strictly meets expected risk score bounds!", icon="🏆")
    else:
        st.warning(f"⚠️ **{passed_count} of {total_scenarios} Scenarios Passed Expected Bounds.**")

# Summary Table
summary_rows = []
for r in all_results:
    status_badge = "✅ PASS" if r["passed"] else "❌ FAIL"
    summary_rows.append({
        "ID": r["scenario_id"],
        "Name": r["name"],
        "Class": r["type"],
        "Expected Score": r["expected"],
        "Actual Score": f"{r['actual_score']:.1f} ({r['severity_band'].upper()})",
        "Status": status_badge,
    })

st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 🔬 Scenario Deep Dives & Jump-to-Evidence")

# Scenario Cards
for r in all_results:
    s_id = r["scenario_id"]
    is_malicious = r["type"] == "Malicious"
    header_color = "#e74c3c" if is_malicious else "#27ae60"
    
    with st.container():
        card_col1, card_col2, card_col3 = st.columns([1.5, 4, 1.5])
        
        with card_col1:
            st.markdown(f"#### **{s_id}**")
            st.markdown(f"<span style='color: {header_color}; font-weight: 700;'>{r['type']}</span>", unsafe_allow_html=True)
            st.caption(f"Target: `{r['expected']}`")

        with card_col2:
            st.markdown(f"**{r['name']}**")
            st.markdown(f"*{r['description']}*")
            if s_id == "S4":
                st.caption("🛡️ Notice: Score is low because authorized `approved_travel` context dampened location alerts.")
            elif s_id == "S8":
                st.caption("⚠️ Notice: Score is high because NO travel context was registered. Contrast against S4!")

        with card_col3:
            st.markdown(risk_badge_html(r["actual_score"], r["severity_band"]), unsafe_allow_html=True)
            if r["alert_id"]:
                if st.button("Inspect Evidence 🔍", key=f"s_btn_{s_id}"):
                    st.session_state["selected_alert_id"] = r["alert_id"]
                    st.switch_page("pages/3_Alert_Detail.py")

        st.divider()

conn.close()
