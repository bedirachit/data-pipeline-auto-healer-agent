"""Streamlit entrypoint — login gate, then Dashboard."""

from __future__ import annotations

import streamlit as st

from dashboard.auth import require_login
from dashboard.ui import hide_chrome_for_login, inject_theme

st.set_page_config(
    page_title="ETL Recovery Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

if not st.session_state.get("authenticated"):
    hide_chrome_for_login()
    require_login()
    st.stop()

st.switch_page("pages/1_Dashboard.py")
