"""Agent control — start/stop and chat logs."""

from __future__ import annotations

import html

import streamlit as st

from agent.logging_utils import tail_chat_log
from agent.process_manager import get_status, start_agent, stop_agent
from dashboard.auth import require_login
from dashboard.ui import inject_theme, page_header

st.set_page_config(page_title="Agent | Auto-Healer", page_icon="⚡", layout="wide")
inject_theme()

if not require_login():
    st.stop()

page_header("Agent Control", "Start or stop the multi-pipeline watcher and view chat logs")

status = get_status()

c1, c2, c3 = st.columns(3)
with c1:
    if status["running"]:
        st.markdown('<p class="status-green" style="font-size:1.1rem">● RUNNING</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-red" style="font-size:1.1rem">● STOPPED</p>', unsafe_allow_html=True)
with c2:
    st.metric("Process ID", status.get("pid") or "—")
with c3:
    mode = "Rules-only" if status.get("rules_only") else "Claude + rules fallback"
    st.metric("Mode", mode if status["running"] else "—")

if status.get("started_at"):
    st.caption(f"Started at: {status['started_at']}")

rules_only = st.toggle("Rules-only mode (no Anthropic API key)", value=True)

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Start Agent", disabled=status["running"], use_container_width=True, type="primary"):
        result = start_agent(rules_only=rules_only)
        if result.get("ok"):
            st.success(result["message"])
        else:
            st.warning(result["message"])
        st.rerun()
with col2:
    if st.button("Stop Agent", disabled=not status["running"], use_container_width=True):
        result = stop_agent()
        st.info(result["message"])
        st.rerun()
with col3:
    if st.button("Refresh Logs", use_container_width=True):
        st.rerun()

st.markdown("---")
st.subheader("Agent Chat Log")
st.caption("User and assistant messages only — tool calls are hidden.")

log_text = tail_chat_log(max_lines=300)
st.markdown(f'<div class="log-panel">{html.escape(log_text)}</div>', unsafe_allow_html=True)

st.caption("Process output: `agent/audit/agent_process.log`")
