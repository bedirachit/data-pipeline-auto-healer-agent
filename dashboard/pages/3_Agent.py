"""Agent control — start/stop and chat logs."""

from __future__ import annotations

import html
from datetime import timedelta

import streamlit as st

from agent.logging_utils import clear_chat_log, tail_chat_log
from agent.process_manager import get_status, start_agent, stop_agent
from dashboard.auth import require_login
from dashboard.ui import format_utc_datetime, inject_theme, page_header, render_app_sidebar

st.set_page_config(page_title="Agent | ETL Recovery Agent", page_icon="⚡", layout="wide")
inject_theme()

if not require_login():
    st.stop()

render_app_sidebar()
page_header("Agent Control", "Start or stop the multi-pipeline watcher and view chat logs")

st.markdown(
    """
    <style>
    div.st-key-start_agent button,
    div.st-key-stop_agent button {
        width: 100% !important;
        min-width: 7rem !important;
        max-width: 9rem !important;
        padding: 0.5rem 1rem !important;
        margin-top: 0.15rem !important;
    }
    div.st-key-start_agent button {
        background: linear-gradient(180deg, #22c55e, #16a34a) !important;
        border-color: #22c55e !important;
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    div.st-key-start_agent button:hover {
        background: linear-gradient(180deg, #16a34a, #15803d) !important;
        border-color: #16a34a !important;
    }
    div.st-key-stop_agent button {
        background: linear-gradient(180deg, #ef4444, #dc2626) !important;
        border-color: #ef4444 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    div.st-key-stop_agent button:hover {
        background: linear-gradient(180deg, #dc2626, #b91c1c) !important;
        border-color: #dc2626 !important;
    }
    div.st-key-clear_chat_log button {
        width: 2rem !important;
        min-width: 2rem !important;
        max-width: 2rem !important;
        height: 2rem !important;
        padding: 0 !important;
        font-size: 1rem !important;
        line-height: 1 !important;
        background: transparent !important;
        border: 1px solid #3a5a80 !important;
        color: #94b8d9 !important;
    }
    div.st-key-clear_chat_log button:hover {
        background: #2a1a20 !important;
        border-color: #ef4444 !important;
        color: #ff6b7a !important;
    }
    div.st-key-clear_chat_log [data-testid="stColumn"] {
        margin-top: 0.15rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _format_started(iso: str | None) -> str:
    return format_utc_datetime(iso, include_seconds=False)


flash = st.session_state.pop("agent_flash", None)
if flash:
    if flash.get("ok"):
        st.success(flash["message"])
    else:
        st.warning(flash["message"])

status = get_status()
running = status["running"]
pid = status.get("pid") or "—"
started = _format_started(status.get("started_at"))
status_class = "status-green" if running else "status-red"
status_label = "RUNNING" if running else "STOPPED"

card_col, btn_col = st.columns([6, 1], vertical_alignment="center")
with card_col:
    st.markdown(
        f"""
        <div class="agent-status-card" style="margin-bottom:0">
          <p class="status-line {status_class}">● {status_label}</p>
          <p class="meta-row">
            <span>PID <code>{html.escape(str(pid))}</code></span>
            <span>Started {html.escape(started)}</span>
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with btn_col:
    if running:
        if st.button("Stop Agent", key="stop_agent", type="primary"):
            result = stop_agent()
            st.session_state["agent_flash"] = result
            st.rerun()
    else:
        if st.button("Start Agent", key="start_agent", type="primary"):
            result = start_agent()
            st.session_state["agent_flash"] = result
            st.rerun()

st.markdown('<div style="height:1.25rem"></div>', unsafe_allow_html=True)
log_title, log_clear, _ = st.columns([0.18, 0.04, 0.78], gap="small", vertical_alignment="center")
with log_title:
    st.markdown(
        '<p style="font-size:1.35rem;font-weight:600;color:#fafafa;margin:0;padding:0;">'
        "Agent Chat Log</p>",
        unsafe_allow_html=True,
    )
with log_clear:
    if st.button("🗑️", key="clear_chat_log", help="Clear chat log"):
        clear_chat_log()
        st.rerun()


@st.fragment(run_every=timedelta(seconds=2))
def log_panel() -> None:
    log_text = tail_chat_log(max_lines=300)
    if not log_text.strip() or log_text.startswith("No agent chat logs"):
        st.markdown(
            '<div class="log-panel" style="color:#94b8d9;font-style:italic">'
            "Waiting for agent activity…"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    formatted = []
    for line in log_text.splitlines():
        escaped = html.escape(line)
        if "] TOOL:" in line:
            escaped = f'<span style="color:#00c8ff;font-weight:600">{escaped}</span>'
        formatted.append(escaped)
    st.markdown(f'<div class="log-panel">{"<br>".join(formatted)}</div>', unsafe_allow_html=True)


log_panel()
