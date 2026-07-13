"""Structured console and chat logging for the auto-healer agent."""

from __future__ import annotations

from datetime import datetime, timezone

from agent.config import CHAT_LOG


def log(stage: str, message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] [{stage}] {message}", flush=True)


def chat_log(role: str, message: str) -> None:
    """Append user/assistant text to agent_chat.log for dashboard display."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {role.upper()}: {message.strip()}\n"
    CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CHAT_LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    log(role, message[:200])


def tail_chat_log(max_lines: int = 200) -> str:
    if not CHAT_LOG.exists():
        return "No agent chat logs yet. Start the agent and trigger a failure."
    lines = CHAT_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-max_lines:])
