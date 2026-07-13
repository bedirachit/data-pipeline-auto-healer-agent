"""Pipeline configuration — add, test, save, manage."""

from __future__ import annotations

import streamlit as st

from agent.pipeline_registry import (
    PipelineConfig,
    delete_pipeline,
    list_pipelines,
    save_pipeline,
    test_connection,
)
from dashboard.auth import require_login
from dashboard.ui import inject_theme, page_header, render_pipeline_cards

st.set_page_config(page_title="Pipelines | Auto-Healer", page_icon="⚡", layout="wide")
inject_theme()

if not require_login():
    st.stop()

page_header("Pipeline Config", "Register Snowflake dbt projects and link GitHub repos")

if "test_passed" not in st.session_state:
    st.session_state.test_passed = False
if "edit_pipeline" not in st.session_state:
    st.session_state.edit_pipeline = None
if "show_add_form" not in st.session_state:
    st.session_state.show_add_form = False
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None

pipelines = list_pipelines()
edit = st.session_state.edit_pipeline
form_open = st.session_state.show_add_form or edit is not None

# ── Toolbar ──
tb1, tb2, _ = st.columns([1, 1, 4])
with tb1:
    if st.button("＋ Add pipeline", type="primary", disabled=form_open):
        st.session_state.show_add_form = True
        st.session_state.edit_pipeline = None
        st.session_state.test_passed = False
        st.rerun()
with tb2:
    if form_open and st.button("Cancel"):
        st.session_state.show_add_form = False
        st.session_state.edit_pipeline = None
        st.session_state.test_passed = False
        st.rerun()

# ── Add / Edit form ──
if form_open:
    title = "Edit Pipeline" if edit else "Add Pipeline"
    st.markdown(f"#### {title}")

    defaults = edit or {}
    with st.form("pipeline_form"):
        c1, c2 = st.columns(2)
        with c1:
            dbt_name = st.text_input(
                "DBT Project Name",
                value=defaults.get("dbt_name", ""),
                placeholder="SNOWFLAKES_SALES",
            )
            snowflake_database = st.text_input(
                "Snowflake Database",
                value=defaults.get("snowflake_database", "DEMO_DB"),
            )
            github_repo_url = st.text_input(
                "GitHub Repo URL",
                value=defaults.get("github_repo_url", ""),
                placeholder="https://github.com/org/repo",
            )
        with c2:
            pipeline_id = st.text_input(
                "Pipeline ID",
                value=defaults.get("pipeline_id", ""),
                placeholder="auto-generated from dbt name",
                disabled=edit is not None,
            )
            snowflake_schema = st.text_input(
                "Snowflake Schema",
                value=defaults.get("snowflake_schema", "DEMO_SCHEMA"),
            )
            model_file_path = st.text_input(
                "Model File Path",
                value=defaults.get(
                    "model_file_path", "pipeline/dbt/models/marts/sales_summary.sql"
                ),
            )

        btn1, btn2, _ = st.columns([1, 1, 2])
        test_btn = btn1.form_submit_button("Test Connection")
        save_btn = btn2.form_submit_button("Save", type="primary")

        draft = {
            "dbt_name": dbt_name,
            "snowflake_database": snowflake_database,
            "snowflake_schema": snowflake_schema,
            "github_repo_url": github_repo_url,
            "model_file_path": model_file_path,
            "pipeline_id": (pipeline_id or defaults.get("pipeline_id") or "").strip() or None,
        }

        if test_btn:
            if not dbt_name or not github_repo_url:
                st.error("DBT name and GitHub URL are required.")
            else:
                cfg = PipelineConfig(
                    pipeline_id=draft["pipeline_id"] or dbt_name.lower(),
                    dbt_name=dbt_name,
                    snowflake_database=snowflake_database,
                    snowflake_schema=snowflake_schema,
                    github_repo_url=github_repo_url,
                    model_file_path=model_file_path,
                )
                result = test_connection(cfg)
                for msg in result["messages"]:
                    if "error" in msg.lower() or "not found" in msg.lower():
                        st.warning(msg)
                    else:
                        st.success(msg)
                st.session_state.test_passed = result["ok"]

        if save_btn:
            if not st.session_state.get("test_passed"):
                st.error("Run **Test Connection** successfully before saving.")
            elif not dbt_name or not github_repo_url:
                st.error("DBT name and GitHub URL are required.")
            else:
                save_pipeline(**draft)
                st.session_state.test_passed = False
                st.session_state.show_add_form = False
                st.session_state.edit_pipeline = None
                st.success(f"Saved pipeline `{draft['pipeline_id'] or dbt_name.lower()}`")
                st.rerun()

    st.markdown("---")

# ── Registered pipelines (cards with inline actions) ──
st.markdown(f"#### Registered Pipelines ({len(pipelines)})")


def _on_edit(pipeline_id: str) -> None:
    p = next((x for x in pipelines if x.pipeline_id == pipeline_id), None)
    if p:
        st.session_state.edit_pipeline = p.to_dict()
        st.session_state.show_add_form = False
        st.session_state.test_passed = False
        st.rerun()


def _on_delete_request(pipeline_id: str) -> None:
    st.session_state.confirm_delete_id = pipeline_id


def _on_delete_confirm(pipeline_id: str) -> None:
    delete_pipeline(pipeline_id)
    st.session_state.confirm_delete_id = None
    if (
        st.session_state.edit_pipeline
        and st.session_state.edit_pipeline.get("pipeline_id") == pipeline_id
    ):
        st.session_state.edit_pipeline = None
    st.rerun()


def _on_delete_cancel() -> None:
    st.session_state.confirm_delete_id = None
    st.rerun()


render_pipeline_cards(
    pipelines,
    on_edit=_on_edit,
    on_delete_request=_on_delete_request,
    on_delete_confirm=_on_delete_confirm,
    on_delete_cancel=_on_delete_cancel,
    confirm_delete_id=st.session_state.confirm_delete_id,
)
