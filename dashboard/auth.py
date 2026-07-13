"""Admin authentication for Streamlit dashboard."""

from __future__ import annotations

import streamlit as st

from agent.config import env
from dashboard.ui import hide_chrome_for_login


def check_credentials(username: str, password: str) -> bool:
    admin_user = env("ADMIN_USERNAME", "admin")
    admin_pass = env("ADMIN_PASSWORD", "admin")
    return username == admin_user and password == admin_pass


def require_login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    hide_chrome_for_login()

    _, col, _ = st.columns([0.75, 1.6, 0.75])
    with col:
        st.markdown(
            """
            <div class="login-brand" style="text-align:center;margin-bottom:1rem;">
              <div style="font-size:2.5rem;line-height:1;">⚡</div>
              <h1 style="font-size:1.4rem;font-weight:700;color:#fff;margin:0.5rem 0 0.25rem;">ETL Recovery Agent</h1>
              <p style="color:#7a9fbf;font-size:0.9rem;margin:0;">Sign in</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="admin")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
                if submitted:
                    if check_credentials(username, password):
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.switch_page("pages/1_Dashboard.py")
                    else:
                        st.error("Invalid username or password")

    return False


def logout_button() -> None:
    if st.sidebar.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()
