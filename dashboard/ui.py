"""Shared UI helpers — theme injection and layout."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st

THEME_PATH = Path(__file__).parent / "theme.css"


def inject_theme() -> None:
    css = THEME_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def hide_chrome_for_login() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="stSidebarNav"] { display: none !important; }
            button[kind="header"] { display: none !important; }
            [data-testid="collapsedControl"] { display: none !important; }
            .block-container { padding-top: 2rem !important; max-width: 720px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_pipeline_cards(
    pipelines,
    on_edit: Callable[[str], None],
    on_delete_request: Callable[[str], None],
    on_delete_confirm: Callable[[str], None],
    on_delete_cancel: Callable[[], None],
    confirm_delete_id: str | None = None,
) -> None:
    """Pipeline list as cards with inline View details, Edit, Delete."""
    if not pipelines:
        st.info("No pipelines yet. Click **Add pipeline** above to register one.")
        return

    for p in pipelines:
        enabled_badge = "🟢 Active" if p.enabled else "⚪ Disabled"
        with st.container(border=True):
            head_l, head_r = st.columns([5, 2])
            with head_l:
                st.markdown(f"**{p.dbt_name}**")
                st.caption(
                    f"`{p.pipeline_id}` · {p.snowflake_database}.{p.snowflake_schema} · {enabled_badge}"
                )
            with head_r:
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Edit", key=f"edit_{p.pipeline_id}", use_container_width=True):
                        on_edit(p.pipeline_id)
                with b2:
                    if st.button("Delete", key=f"del_{p.pipeline_id}", use_container_width=True):
                        on_delete_request(p.pipeline_id)

            with st.expander("View details", expanded=False):
                st.markdown(
                    f"""
| Field | Value |
|-------|-------|
| **Pipeline ID** | `{p.pipeline_id}` |
| **DBT project** | `{p.dbt_name}` |
| **Snowflake** | `{p.snowflake_database}.{p.snowflake_schema}.{p.dbt_name}` |
| **GitHub repo** | [{p.github_repo_url}]({p.github_repo_url}) |
| **Model file** | `{p.model_file_path}` |
| **Registered** | {p.created_at[:19] if p.created_at else "—"} |
                    """
                )

            if confirm_delete_id == p.pipeline_id:
                st.warning(f"Delete **{p.dbt_name}** (`{p.pipeline_id}`)? This cannot be undone.")
                c1, c2, _ = st.columns([1, 1, 3])
                with c1:
                    if st.button("Yes, delete", key=f"confirm_{p.pipeline_id}", type="primary"):
                        on_delete_confirm(p.pipeline_id)
                with c2:
                    if st.button("Cancel", key=f"cancel_{p.pipeline_id}"):
                        on_delete_cancel()


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<p class="hero-title">{title}</p>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="subtitle">{subtitle}</p>', unsafe_allow_html=True)
