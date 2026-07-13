"""Agent safety and audit hooks for Claude Agent SDK."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent.config import AUDIT_LOG, PROJECT_ROOT
from agent.logging_utils import log, tool_log

SENSITIVE_FILES = {".env", ".env.local"}
ALLOWED_WRITE_PREFIXES = (
    "pipeline/sql/",
    "pipeline/dags/",
)

_pr_timestamps: dict[str, float] = {}


def _append_audit(record: dict) -> None:
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _redact_args(tool_input: dict) -> dict:
    redacted = dict(tool_input)
    for key in ("password", "token", "secret"):
        if key in redacted:
            redacted[key] = "***"
    return redacted


async def audit_log_pre(input_data, tool_use_id, context):
    tool = input_data.get("tool_name", "")
    log("audit", f"Tool call: {tool}")
    tool_log(tool)
    _append_audit(
        {
            "event": "PreToolUse",
            "tool": input_data.get("tool_name"),
            "input": _redact_args(input_data.get("tool_input", {})),
        }
    )
    return {}


async def audit_log_post(input_data, tool_use_id, context):
    _append_audit(
        {
            "event": "PostToolUse",
            "tool": input_data.get("tool_name"),
        }
    )
    return {}


async def block_secrets(input_data, tool_use_id, context):
    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return {}

    file_path = input_data.get("tool_input", {}).get("file_path", "")
    name = Path(file_path).name
    if name in SENSITIVE_FILES or ".env" in file_path:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": "Cannot modify secret/env files",
            }
        }
    return {}


async def pr_guard(input_data, tool_use_id, context):
    if input_data.get("tool_name") != "mcp__healer__create_fix_pr":
        return {}

    args = input_data.get("tool_input", {})
    branch = args.get("branch_name", "")
    body = args.get("body", "")
    incident = args.get("incident_id", "")

    if not branch.startswith("auto-heal/"):
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": "Branch must start with auto-heal/",
            }
        }
    if not incident or incident not in body:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": "PR body must cite incident_id",
            }
        }
    return {}


async def rate_limit_pr(input_data, tool_use_id, context):
    if input_data.get("tool_name") != "mcp__healer__create_fix_pr":
        return {}

    incident = input_data.get("tool_input", {}).get("incident_id", "")
    now = datetime.now(timezone.utc).timestamp()
    last = _pr_timestamps.get(incident, 0)
    if now - last < 3600:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": "Rate limit: one PR per incident per hour",
            }
        }
    _pr_timestamps[incident] = now
    return {}


def build_hooks():
    from claude_agent_sdk import HookMatcher

    return {
        "PreToolUse": [
            HookMatcher(hooks=[audit_log_pre]),
            HookMatcher(matcher="Write|Edit", hooks=[block_secrets]),
            HookMatcher(matcher="mcp__healer__create_fix_pr", hooks=[pr_guard, rate_limit_pr]),
        ],
        "PostToolUse": [HookMatcher(hooks=[audit_log_post])],
    }
