"""Claude Agent SDK runner for pipeline auto-healing."""

from __future__ import annotations

import asyncio
import json

from agent.config import PROJECT_ROOT
from agent.hooks.safety import build_hooks
from agent.logging_utils import chat_log, log
from agent.mcp_server import build_mcp_server
from agent.pipeline_registry import PipelineConfig, get_pipeline
from agent.rule_healer import heal_with_rules, _get_model_sql
from agent.tools import github_tools

SYSTEM_PROMPT = (PROJECT_ROOT / "agent" / "prompts" / "system.md").read_text(encoding="utf-8")

MCP_TOOLS = [
    "mcp__healer__describe_table",
    "mcp__healer__get_lineage",
    "mcp__healer__create_fix_pr",
]


def _resolve_pipeline(failure: dict) -> PipelineConfig | None:
    pid = failure.get("pipeline_id", "")
    if pid:
        return get_pipeline(pid)
    from agent.pipeline_registry import list_pipelines

    pipelines = list_pipelines(enabled_only=True)
    return pipelines[0] if pipelines else None


def _build_prompt(failure: dict, pipeline: PipelineConfig) -> str:
    model_sql = _get_model_sql(pipeline)
    return f"""
A new dbt pipeline failure was detected by the watcher. Diagnose and open a fix PR.

## Pipeline
- ID: {pipeline.pipeline_id}
- dbt project: {pipeline.dbt_name}
- GitHub: {pipeline.github_repo_url}
- Model file: {pipeline.model_file_path}

## Failure (already detected — do NOT re-fetch failures)
{json.dumps(failure, default=str, indent=2)}

## Current model SQL ({pipeline.model_file_path})
```sql
{model_sql}
```

Use `describe_table` on `raw_sales` (database {pipeline.snowflake_database}, schema {pipeline.snowflake_schema}) to confirm the live schema.
Use `get_lineage` if helpful for upstream context.
Patch the model SQL and call `create_fix_pr` with repo_name `{pipeline.github_repo_slug}` and file path `{pipeline.model_file_path}` — do not run dbt or execute anything in Snowflake.
"""


def _extract_chat_from_message(message) -> None:
    """Extract user/assistant text from Claude SDK messages."""
    content = getattr(message, "content", None)
    if content is None:
        return
    role = "assistant"
    if type(message).__name__ == "UserMessage":
        role = "user"
    if isinstance(content, str):
        chat_log(role, content)
        return
    if not isinstance(content, list):
        return
    for block in content:
        block_type = type(block).__name__
        if block_type == "TextBlock":
            text = getattr(block, "text", "")
            if text.strip():
                chat_log(role, text.strip())
        elif block_type == "ToolUseBlock":
            pass  # logged via PreToolUse hook
        elif block_type == "ToolResultBlock":
            pass  # skip tool results


async def run_claude_agent(failure: dict, pipeline: PipelineConfig) -> None:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    query_id = failure.get("query_id", "unknown")
    log("heal", f"[{pipeline.pipeline_id}] Starting Claude agent for query_id={query_id}")
    chat_log("user", f"New failure on {pipeline.dbt_name} — investigate and open fix PR.")

    server = build_mcp_server()
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"healer": server},
        allowed_tools=MCP_TOOLS,
        hooks=build_hooks(),
        cwd=str(PROJECT_ROOT),
    )

    prompt = _build_prompt(failure, pipeline)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            _extract_chat_from_message(message)


def heal_failure(
    failure: dict,
    pipeline: PipelineConfig | None = None,
    use_claude: bool = True,
) -> dict | None:
    """Heal a single failure via Claude agent or rule fallback."""
    pipeline = pipeline or _resolve_pipeline(failure)
    if pipeline is None:
        log("heal", "No pipeline config for failure")
        return None

    query_id = failure.get("query_id", "unknown")
    if use_claude:
        try:
            asyncio.run(run_claude_agent(failure, pipeline))
            log("heal", f"Claude agent finished for query_id={query_id}")
            return {"mode": "claude_agent", "query_id": query_id, "pipeline_id": pipeline.pipeline_id}
        except Exception as exc:
            log("heal", f"Claude agent failed ({exc}), falling back to rules")
            chat_log("assistant", f"Claude agent failed, falling back to rules: {exc}")
    log("heal", f"Running rule-based healer for query_id={query_id}")
    return heal_with_rules(failure, pipeline)
