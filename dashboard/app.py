"""Streamlit admin dashboard entrypoint."""

from __future__ import annotations

import streamlit as st

from dashboard.auth import logout_button, require_login
from dashboard.ui import hide_chrome_for_login, inject_theme, page_header

st.set_page_config(
    page_title="Pipeline Auto-Healer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

if not st.session_state.get("authenticated"):
    hide_chrome_for_login()
    require_login()
    st.stop()

st.sidebar.markdown("### ⚡ Auto-Healer")
st.sidebar.caption(f"Signed in as **{st.session_state.get('username', 'admin')}**")
st.sidebar.markdown("---")
logout_button()

page_header(
    "Pipeline Command Center",
    "Monitor dbt pipelines · Auto-heal failures · Track PRs & deploys",
)

st.markdown(
    """
    <div style="
        background:#0f1f35;
        border:1px solid #254a70;
        border-radius:12px;
        padding:1rem 1.25rem;
        color:#94b8d9;
        font-size:0.95rem;
    ">
    Use the sidebar to open <strong style="color:#00c8ff">Dashboard</strong>,
    <strong style="color:#00c8ff">Pipelines</strong>, or
    <strong style="color:#00c8ff">Agent</strong>.
    </div>
    """,
    unsafe_allow_html=True,
)
