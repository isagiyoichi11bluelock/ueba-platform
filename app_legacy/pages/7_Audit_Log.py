"""
7_Audit_Log.py - Cryptographic SHA-256 tamper-evident ledger and integrity verifier.
"""
from __future__ import annotations

import json
import sqlite3
import pandas as pd
import streamlit as st

from app_legacy.components import (
    get_db_connection,
    render_header,
    render_role_selector,
)
from src.ueba.audit import verify_audit_chain

render_role_selector()

render_header(
    title="🛡️ Cryptographic Tamper-Evident Audit Ledger",
    subtitle="Immutable SHA-256 Hash Chain Recording Pipeline Runs, Analyst Decisions, and Re-Identifications",
    help_text="""
    **Cryptographic Hash Chain Architecture:**
    - Every log entry computes $\\text{Entry Hash} = \\text{SHA256}(\\text{Previous Hash} + \\text{Canonical JSON}(\\text{Entry}))$.
    - Genesis entry has a previous hash of 64 zeros.
    - Click **'Verify Audit Integrity'** to recalculate every hash across the entire database. If even a single byte or character is modified in SQLite, the verification fails immediately and points to the exact corrupted record ID.
    """,
)

conn = get_db_connection()

# --- Verification Action ---
v_col1, v_col2 = st.columns([1.5, 3.5])

with v_col1:
    verify_clicked = st.button("🔐 Verify Audit Integrity", use_container_width=True)

with v_col2:
    if verify_clicked:
        result = verify_audit_chain(conn)
        if result["valid"]:
            st.success(
                f"✅ **100% INTEGRITY VERIFIED:** All {result['entries_checked']} chained entries validated successfully against SHA-256 signatures. No tampering detected.",
                icon="🔒",
            )
        else:
            st.error(
                f"🚨 **TAMPERING DETECTED!** Hash chain broken at Entry ID: `{result['first_broken_entry']}`. "
                f"Checked {result['entries_checked']} records before integrity failure.",
                icon="⚠️",
            )

st.markdown("<br>", unsafe_allow_html=True)

# --- Audit Records Table ---
try:
    audit_df = pd.read_sql_query(
        "SELECT entry_id, timestamp, actor, action, details_json, prev_hash, entry_hash FROM audit_log ORDER BY timestamp DESC",
        conn,
    )
except Exception as e:
    st.error(f"Error loading audit log: {e}")
    conn.close()
    st.stop()

conn.close()

if audit_df.empty:
    st.info("Audit log is currently empty.")
    st.stop()

# Search filter
search_term = st.text_input("🔍 Search Audit Records (by Actor, Action, or Details)", placeholder="e.g. PIPELINE_RUN, senior_analyst, or REIDENTIFICATION...")

filtered_df = audit_df
if search_term:
    mask = (
        filtered_df["actor"].str.contains(search_term, case=False, na=False)
        | filtered_df["action"].str.contains(search_term, case=False, na=False)
        | filtered_df["details_json"].str.contains(search_term, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

st.markdown(f"**Showing {len(filtered_df)} of {len(audit_df)} Total Audit Entries**")

# Export to CSV
csv_data = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Export Audit Ledger to CSV",
    data=csv_data,
    file_name="ueba_audit_log.csv",
    mime="text/csv",
)

st.dataframe(
    filtered_df[["timestamp", "actor", "action", "details_json", "entry_hash", "prev_hash"]],
    column_config={
        "timestamp": "Timestamp (UTC)",
        "actor": "Actor Identity",
        "action": "Operation / Action",
        "details_json": "Canonical Payload",
        "entry_hash": "SHA-256 Entry Hash",
        "prev_hash": "Parent Hash",
    },
    use_container_width=True,
    hide_index=True,
)
