"""Dashboard — KPIs and pipeline status."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from agent.deploy_checker import refresh_deploy_status
from agent.metrics_store import dashboard_kpis, list_incidents
from agent.pipeline_registry import list_pipelines
from dashboard.auth import require_login
from dashboard.ui import inject_theme, page_header

st.set_page_config(page_title="Dashboard | Auto-Healer", page_icon="⚡", layout="wide")
inject_theme()

if not require_login():
    st.stop()

page_header("Dashboard", "Live status across all tracked dbt pipelines")

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("Refresh status", type="primary"):
        refresh_deploy_status()
        st.rerun()

refresh_deploy_status()

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
        status_label = "🟢 Running"
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
            "Last Failure": latest.get("detected_at", "—")[:19] if latest.get("detected_at") else "—",
            "Last Success": latest.get("last_success_at", "—")[:19] if latest.get("last_success_at") else "—",
            "Open PR": latest.get("pr_url", "—") if latest.get("pr_url") else "—",
            "Time to PR (s)": latest.get("time_to_pr_sec", "—") or "—",
            "Time to Fix (s)": latest.get("time_to_fix_sec", "—") or "—",
        }
    )

if rows:
    st.table(pd.DataFrame(rows))
else:
    st.info("No pipelines registered. Add one on the **Pipelines** page.")

st.subheader("Recent Incidents")
if incidents:
    df = pd.DataFrame(incidents)[
        ["incident_id", "pipeline_id", "detected_at", "error_summary", "status", "deploy_status", "pr_url"]
    ].head(20)
    st.table(df.head(20))
else:
    st.info("No incidents recorded yet.")
