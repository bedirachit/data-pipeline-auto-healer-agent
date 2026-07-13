"""MCP server — Snowflake read-only tools + GitHub PR creation."""

from __future__ import annotations

import json

from claude_agent_sdk import create_sdk_mcp_server, tool

from agent.metrics_store import record_pr_opened
from agent.tools import github_tools, snowflake_tools


@tool(
    "describe_table",
    "Describe columns for a Snowflake table (read-only)",
    {"table_name": str},
)
async def describe_table(args):
    rows = snowflake_tools.describe_table(args["table_name"])
    return {"content": [{"type": "text", "text": json.dumps(rows, indent=2)}]}


@tool(
    "get_lineage",
    "Get upstream lineage for a table (read-only)",
    {"table_name": str},
)
async def get_lineage(args):
    data = snowflake_tools.get_lineage(args["table_name"])
    return {"content": [{"type": "text", "text": json.dumps(data, default=str, indent=2)}]}


@tool(
    "create_fix_pr",
    "Create GitHub branch, commit fix, and open PR",
    {
        "branch_name": str,
        "file_path": str,
        "new_content": str,
        "title": str,
        "body": str,
        "incident_id": str,
        "repo_name": str,
    },
)
async def create_fix_pr(args):
    result = github_tools.create_fix_pr(
        branch_name=args["branch_name"],
        file_path=args["file_path"],
        new_content=args["new_content"],
        title=args["title"],
        body=args["body"],
        incident_id=args["incident_id"],
        repo_name=args.get("repo_name") or None,
    )
    record_pr_opened(args["incident_id"], result["pr_url"], result["pr_number"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


def build_mcp_server():
    return create_sdk_mcp_server(
        name="healer",
        version="1.0.0",
        tools=[
            describe_table,
            get_lineage,
            create_fix_pr,
        ],
    )
