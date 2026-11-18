"""
8_Privacy_and_Limitations.py - Privacy governance, DPDP/GDPR posture, and honest technical limitations.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from app.components import (
    render_header,
    render_role_selector,
)
from src.ueba.config import get_config

render_role_selector()

render_header(
    title="⚖️ Privacy Governance & Technical Limitations",
    subtitle="Data Minimization Safeguards, Legal Foundations, and Honest Operational Boundaries",
    help_text="""
    **Ethics & Governance Posture:**
    - Active settings display confirmed privacy safeguards (IP truncation, HMAC pseudonymization).
    - Full rendered documentation of the platform's privacy architecture and transparent technical boundaries.
    """,
)

cfg = get_config()

# --- Active Privacy Settings Cards ---
st.markdown("### 🔒 Active System Privacy Configurations")

p_c1, p_c2, p_c3, p_c4 = st.columns(4)

with p_c1:
    st.metric("IP Truncation", "Enabled (/24)")
    st.caption("Last octet dropped before database persistence")

with p_c2:
    st.metric("Pseudonymization", "HMAC-SHA256")
    st.caption("Prefix 'U-' with 6-char cryptographic hash")

with p_c3:
    st.metric("Event Retention", f"{cfg.retention.events_days} Days")
    st.caption("Automated raw telemetry expiration")

with p_c4:
    st.metric("Re-ID Clearance", f"{cfg.privacy.identity_map_access_role}")
    st.caption(f"Requires minimum {cfg.privacy.min_justification_chars} chars justification")

st.divider()

# --- Markdown Doc Viewers ---
tab_privacy, tab_limitations = st.tabs(["📜 Privacy Policy & Architecture", "⚠️ Honest Limitations & Threat Model"])

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

with tab_privacy:
    privacy_file = DOCS_DIR / "PRIVACY.md"
    if privacy_file.exists():
        st.markdown(privacy_file.read_text(encoding="utf-8"))
    else:
        st.info("docs/PRIVACY.md not found.")

with tab_limitations:
    limitations_file = DOCS_DIR / "LIMITATIONS.md"
    if limitations_file.exists():
        st.markdown(limitations_file.read_text(encoding="utf-8"))
    else:
        st.info("docs/LIMITATIONS.md not found.")
