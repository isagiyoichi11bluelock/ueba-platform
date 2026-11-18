"""
Reusable Streamlit UI components and layout helpers for the UEBA Platform.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, List, Optional

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "data" / "ueba.db"

SEVERITY_COLORS = {
    "low": "#2ECC71",       # Emerald green
    "medium": "#F39C12",    # Amber
    "high": "#E74C3C",      # Crimson red
    "critical": "#8E44AD",  # Royal purple
}

SEVERITY_BADGES = {
    "low": "🟢 LOW",
    "medium": "🟡 MEDIUM",
    "high": "🔴 HIGH",
    "critical": "🟣 CRITICAL",
}


def get_db_connection() -> sqlite3.Connection:
    """Get SQLite database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def render_banner() -> None:
    """Render the mandatory synthetic demo banner."""
    st.markdown(
        """
        <div style="background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
                    color: #ffffff; padding: 10px 16px; border-radius: 8px;
                    margin-bottom: 20px; font-weight: 600; font-size: 0.9rem;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.15); display: flex;
                    align-items: center; justify-content: space-between;">
            <div>
                <span style="background: #e74c3c; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 8px; font-weight: 700;">DEMO MODE</span>
                ⚠️ SYNTHETIC DATA — DEMO ONLY &nbsp;|&nbsp; All employee identities, events, and IP addresses are randomly generated.
            </div>
            <div style="font-size: 0.8rem; opacity: 0.85;">
                UEBA v1.0 • Privacy Enforced
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str, help_text: Optional[str] = None) -> None:
    """Render consistent page header with subtitle and expandable explanation."""
    render_banner()
    st.title(title)
    if subtitle:
        st.markdown(f"*{subtitle}*")
    if help_text:
        with st.expander("ℹ️ What am I looking at?", expanded=False):
            st.markdown(help_text)
    st.divider()


def render_role_selector() -> str:
    """Sidebar role selector for separation of duties simulation."""
    st.sidebar.markdown("### 👤 User Persona")
    role = st.sidebar.selectbox(
        "Current Active Role",
        options=["analyst", "senior_analyst", "auditor"],
        index=0,
        help="Simulates RBAC. 'senior_analyst' is required for gated re-identification. 'auditor' is read-only.",
    )
    st.sidebar.caption(
        f"Logged in as: **{role}**\n\n*(Production integration uses corporate SSO / SAML / OIDC)*"
    )
    st.sidebar.divider()
    return role


def risk_badge_html(score: float, band: str) -> str:
    """Return inline HTML badge for a given risk score and band."""
    band_lower = band.lower()
    color = SEVERITY_COLORS.get(band_lower, "#95A5A6")
    badge_label = SEVERITY_BADGES.get(band_lower, band.upper())
    return (
        f'<span style="background-color: {color}22; color: {color}; '
        f'border: 1px solid {color}; padding: 3px 10px; border-radius: 12px; '
        f'font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px;">'
        f'{badge_label} ({int(score)})</span>'
    )


def score_gauge(score: float, band: str) -> go.Figure:
    """Create a Plotly semicircular gauge for risk score."""
    color = SEVERITY_COLORS.get(band.lower(), "#3498DB")
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 32, "color": color}},
            title={"text": f"<b>{band.upper()} RISK</b>", "font": {"size": 18}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray"},
                "bar": {"color": color, "thickness": 0.4},
                "bgcolor": "white",
                "steps": [
                    {"range": [0, 34], "color": "rgba(46, 204, 113, 0.15)"},
                    {"range": [35, 59], "color": "rgba(243, 156, 18, 0.15)"},
                    {"range": [60, 79], "color": "rgba(231, 76, 60, 0.15)"},
                    {"range": [80, 100], "color": "rgba(142, 68, 173, 0.15)"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": score,
                },
            },
        )
    )
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def waterfall_score_chart(indicators: List[dict], final_score: float) -> go.Figure:
    """Create a waterfall/bar composition chart showing how indicators build the score."""
    names = []
    points = []
    text = []
    
    for ind in indicators:
        if ind.get("name") == "CHAIN_BONUS":
            for b in ind.get("bonuses", []):
                names.append("Chain Bonus")
                pts = 10.0 if "privilege" in b else (15.0 if "download" in b else 8.0)
                points.append(pts)
                text.append(f"+{pts} pts")
        else:
            names.append(ind.get("name", "Indicator").replace("_", " ").title())
            pts = float(ind.get("severity_points", 0))
            points.append(pts)
            text.append(f"{pts:.1f} pts")
    
    if not names:
        names = ["Baseline"]
        points = [final_score]
        text = [f"{final_score}"]

    fig = go.Figure(
        go.Bar(
            x=names,
            y=points,
            text=text,
            textposition="auto",
            marker_color="#3498DB",
        )
    )
    fig.update_layout(
        title="<b>Risk Score Composition (Indicator Contributions)</b>",
        yaxis_title="Severity Points",
        xaxis_tickangle=-30,
        height=320,
        margin=dict(l=20, r=20, t=40, b=60),
    )
    return fig
