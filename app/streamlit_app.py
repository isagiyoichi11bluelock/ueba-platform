"""
streamlit_app.py - Main entry point and executive home page for the UEBA Platform.

Run with:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
import streamlit as st

from app.components import (
    get_db_connection,
    render_header,
    render_role_selector,
    risk_badge_html,
)

st.set_page_config(
    page_title="UEBA Platform — Insider Threat Analytics",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    role = render_role_selector()

    render_header(
        title="🛡️ Insider Threat & User Behavior Analytics (UEBA)",
        subtitle="Explainable, Context-Aware, Privacy-Preserving Behavioral Detection Engine",
        help_text="""
        **Welcome to the UEBA Platform Demonstration.**
        
        This enterprise prototype analyzes workforce behavior patterns to identify compromised accounts,
        privilege misuse, and anomalous data egress without invasive surveillance.
        
        **Key Principles:**
        - **An anomaly is not proof of wrongdoing.** Benign context dampening reduces false positives for approved travel or on-call emergencies.
        - **Data Minimization:** No cleartext employee names, emails, or complete IPs are stored or displayed in the analyst interface.
        - **Explainable by Design:** Every alert is broken down into specific rule-based indicators linking directly to raw audit event IDs.
        """,
    )

    col1, col2, col3, col4 = st.columns(4)

    # Fetch high level metrics if DB exists
    total_alerts = 0
    critical_alerts = 0
    reviewed_alerts = 0
    total_events = 0

    try:
        conn = get_db_connection()
        total_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        critical_alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE severity_band = 'critical'").fetchone()[0]
        reviewed_alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE status != 'open'").fetchone()[0]
        
        l_cnt = conn.execute("SELECT COUNT(*) FROM login_events").fetchone()[0]
        f_cnt = conn.execute("SELECT COUNT(*) FROM file_access_events").fetchone()[0]
        d_cnt = conn.execute("SELECT COUNT(*) FROM download_events").fetchone()[0]
        p_cnt = conn.execute("SELECT COUNT(*) FROM privilege_events").fetchone()[0]
        total_events = l_cnt + f_cnt + d_cnt + p_cnt
        conn.close()
    except Exception:
        pass

    with col1:
        st.metric("Total Events Ingested", f"{total_events:,}")
    with col2:
        st.metric("Active Alerts", f"{total_alerts}")
    with col3:
        st.metric("Critical Alerts", f"{critical_alerts}")
    with col4:
        st.metric("Analyst Reviews Completed", f"{reviewed_alerts}")

    st.markdown("### 🧭 Platform Navigation Guide")
    
    nav_c1, nav_c2, nav_c3 = st.columns(3)
    
    with nav_c1:
        st.markdown(
            """
            #### 🔍 Threat Detection & Triage
            - **[1. Overview](Overview)**: Global SOC risk posture, heatmaps, and score distribution.
            - **[2. Alert Queue](Alert_Queue)**: Interactive triage queue with multi-factor filters.
            - **[3. Alert Detail](Alert_Detail)**: The **Hero View** with indicator cards and evidence links.
            """
        )
    with nav_c2:
        st.markdown(
            """
            #### 📈 Behavioral Baselines & Deep Dives
            - **[4. User Timeline](User_Timeline)**: Day-by-day activity maps and anomaly highlights.
            - **[5. Baselines](Baselines)**: User vs role-peer baseline comparison radar.
            - **[6. Scenarios Demo](Scenarios_Demo)**: One-click live demonstration of scenarios **S1–S8**.
            """
        )
    with nav_c3:
        st.markdown(
            """
            #### ⚖️ Governance, Privacy & Audit
            - **[7. Audit Log](Audit_Log)**: Cryptographic SHA-256 tamper-evident ledger verification.
            - **[8. Privacy & Limitations](Privacy_and_Limitations)**: DPDP/GDPR compliance and threat modeling.
            - **[9. Model Evaluation](Model_Evaluation)**: Confusion matrix and precision/recall on ground truth.
            """
        )

    st.info(
        "💡 **Quick Pitch Tip:** For a 5-minute judge walkthrough, head straight to **Page 6: Scenarios Demo** "
        "to run scenarios S1 through S8 and see live contrast between malicious attacks and context-dampened benign exceptions.",
        icon="🚀",
    )


if __name__ == "__main__":
    main()
