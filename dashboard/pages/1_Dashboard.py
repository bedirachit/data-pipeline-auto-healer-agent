"""Dashboard — KPIs and pipeline status."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from agent.deploy_checker import refresh_deploy_status
from agent.metrics_store import dashboard_kpis, list_incidents
from agent.pipeline_registry import list_pipelines
from dashboard.auth import require_login
from dashboard.ui import format_utc_datetime, inject_theme, page_header, render_app_sidebar


def _format_downtime_minutes(sec_str: str) -> str:
    if not sec_str or sec_str == "—":
        return "—"
    try:
        minutes = int(sec_str) / 60
        return f"{minutes:.1f} min" if minutes < 10 else f"{minutes:.0f} min"
    except (TypeError, ValueError):
        return "—"


def _format_time_to_pr(sec_str: str) -> str:
    if not sec_str or sec_str == "—":
        return "—"
    try:
        return f"{int(sec_str)} s"
    except (TypeError, ValueError):
        return "—"

st.set_page_config(page_title="Dashboard | Auto-Healer", page_icon="⚡", layout="wide")
inject_theme()

if not require_login():
    st.stop()

render_app_sidebar()
page_header("Dashboard", "Live status across all tracked dbt pipelines")

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("Refresh status", type="primary"):
        try:
            n = refresh_deploy_status()
            st.success(f"Updated {n} incident(s).")
        except Exception as exc:
            st.error(f"Could not refresh from Snowflake: {exc}")
        st.rerun()

try:
    refresh_deploy_status()
except Exception as exc:
    st.error(f"Could not refresh deploy status from Snowflake: {exc}")

pipelines = list_pipelines()
kpis = dashboard_kpis()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Tracked Pipelines", len(pipelines))
m2.metric("Open Failures", kpis["open_failures"])
m3.metric("PRs Opened", kpis["prs_opened"])
m4.metric("Deployed Fixes", kpis["deployed_fixes"])
avg = kpis["avg_time_to_pr_sec"]
m5.metric("Avg Time to PR", f"{avg}s" if avg else "—")

st.markdown("---")
st.subheader("Pipeline Status")

incidents = list_incidents()
rows = []
for p in pipelines:
    pipe_incidents = sorted(
        [i for i in incidents if i.get("pipeline_id") == p.pipeline_id],
        key=lambda x: x.get("detected_at", ""),
        reverse=True,
    )
    latest = pipe_incidents[0] if pipe_incidents else {}
    deploy = latest.get("deploy_status", "—")
    if not pipe_incidents:
        status_label = "🟢 Idle"
    elif deploy == "green":
        status_label = "🟢 OK"
    elif deploy == "red":
        status_label = "🔴 Failed"
    elif latest.get("status") in ("open", "pr_opened"):
        status_label = "🟡 Healing"
    else:
        status_label = "⚪ Unknown"

    rows.append(
        {
            "Pipeline": p.dbt_name,
            "ID": p.pipeline_id,
            "Status": status_label,
            "Last Failure": format_utc_datetime(latest.get("detected_at")),
            "Last Success": format_utc_datetime(latest.get("last_success_at")),
        }
    )

if rows:
    st.table(pd.DataFrame(rows))
else:
    st.info("No pipelines registered. Add one on the **Pipelines** page.")

st.subheader("Recent Incidents")
if incidents:
    df = pd.DataFrame(incidents)[
        [
            "incident_id",
            "pipeline_id",
            "detected_at",
            "error_summary",
            "status",
            "deploy_status",
            "pr_url",
            "time_to_pr_sec",
            "time_to_fix_sec",
        ]
    ].head(20)
    df["detected_at"] = df["detected_at"].apply(format_utc_datetime)
    df["status"] = df["status"].replace({"deployed": "RESOLVED"})
    df["time_to_pr_sec"] = df["time_to_pr_sec"].apply(_format_time_to_pr)
    df["time_to_fix_sec"] = df["time_to_fix_sec"].apply(_format_downtime_minutes)
    df = df.rename(
        columns={
            "incident_id": "Incident ID",
            "pipeline_id": "Pipeline ID",
            "detected_at": "Detected At",
            "error_summary": "Error Summary",
            "status": "Status",
            "deploy_status": "Deploy Status",
            "pr_url": "PR URL",
            "time_to_pr_sec": "Time to PR",
            "time_to_fix_sec": "Downtime",
        }
    )
    st.table(df.head(20))
else:
    st.info("No incidents recorded yet.")
