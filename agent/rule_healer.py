"""Rule-based fallback healer when running heal-once without full agent loop."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any

from agent.logging_utils import chat_log, log
from agent.metrics_store import record_pr_opened
from agent.pipeline_registry import PipelineConfig, get_pipeline
from agent.tools import github_tools, repo_tools, snowflake_tools


@dataclass
class FixResult:
    new_sql: str
    issue_type: str
    summary: str
    diagnosis: str
    fix_applied: str


def _get_model_sql(pipeline: PipelineConfig) -> str:
    try:
        return github_tools.fetch_file_content(
            pipeline.github_repo_slug, pipeline.model_file_path
        )
    except Exception as exc:
        log("rules", f"GitHub fetch failed ({exc}), using local model file")
        return repo_tools.read_pipeline_sql()


def _fix_schema_drift(sql: str, error: str, columns: list[dict]) -> FixResult | None:
    match = re.search(r"invalid identifier '([^']+)'", error, re.I)
    if not match:
        match = re.search(r"'([^']+)' does not exist", error, re.I)
    if not match:
        return None

    missing = match.group(1)
    missing_lower = missing.lower()
    col_names = [c.get("name", c.get("column_name", "")) for c in columns]
    col_names_lower = [c.lower() for c in col_names]

    replacement = None
    for col, col_lower in zip(col_names, col_names_lower):
        if (
            missing_lower in col_lower
            or col_lower in missing_lower
            or (missing_lower == "qty" and col_lower == "quantity")
        ):
            replacement = col
            break
    if not replacement:
        return None

    pattern = re.compile(re.escape(missing), re.I)
    new_sql = pattern.sub(replacement, sql)
    if new_sql == sql:
        return None

    actual_cols = ", ".join(f"`{c}`" for c in col_names)
    return FixResult(
        new_sql=new_sql,
        issue_type="Schema drift",
        summary=f"Column `{missing}` no longer exists — renamed to `{replacement}`",
        diagnosis=(
            f"The dbt model references column **`{missing}`**, but `raw_sales` no longer "
            f"has that column.\n\n"
            f"Current columns in `raw_sales`: {actual_cols}.\n\n"
            f"Snowflake error: `invalid identifier '{missing.upper()}'` — the source table "
            f"schema changed (likely `{missing}` renamed to `{replacement}`)."
        ),
        fix_applied=(
            f"Updated model to use **`{replacement}`** instead of **`{missing}`**."
        ),
    )


def _fix_divide_by_zero(sql: str, error: str) -> FixResult | None:
    if "division by zero" not in error.lower() and "divide by zero" not in error.lower():
        return None
    if "nullif" in sql.lower():
        return None

    new_sql = re.sub(
        r"sum\s*\(\s*qty\s*/\s*\(\s*user_id\s*-\s*100\s*\)\s*\)",
        "sum(qty / nullif(user_id - 100, 0))",
        sql,
        flags=re.I,
    )
    if new_sql == sql:
        return None

    return FixResult(
        new_sql=new_sql,
        issue_type="Divide by zero",
        summary="Division by zero when `user_id = 100`",
        diagnosis=(
            "The model divides by `(user_id - 100)`. When `user_id` equals 100, "
            "the divisor is zero and Snowflake raises a divide-by-zero error."
        ),
        fix_applied=(
            "Wrapped the divisor with `nullif(user_id - 100, 0)` so zero divisors "
            "return NULL instead of failing the run."
        ),
    )


def _fix_sql_syntax(sql: str, error: str) -> FixResult | None:
    if "syntax error" not in error.lower():
        return None

    new_sql = re.sub(
        r"user_id\s+sum\s*\(",
        "user_id,\n    sum(",
        sql,
        flags=re.I,
    )
    if new_sql == sql:
        return None

    return FixResult(
        new_sql=new_sql,
        issue_type="SQL syntax error",
        summary="Missing comma between SELECT columns",
        diagnosis=(
            "The SELECT list is missing a comma between `user_id` and `sum(...)`, "
            "causing a SQL compilation syntax error."
        ),
        fix_applied="Added the missing comma after `user_id` in the SELECT clause.",
    )


def _build_pr_body(failure: dict[str, Any], fix: FixResult, old_sql: str, pipeline: PipelineConfig) -> str:
    query_id = failure.get("query_id", "unknown")
    error = failure.get("error_message", "")
    start_time = failure.get("start_time", "")

    diff = "\n".join(
        difflib.unified_diff(
            old_sql.splitlines(),
            fix.new_sql.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )

    lines = [
        "## Auto-heal summary",
        "",
        f"**Pipeline:** `{pipeline.dbt_name}` ({pipeline.pipeline_id})",
        f"**Issue:** {fix.issue_type} — {fix.summary}",
        "",
        "### Diagnosis",
        fix.diagnosis,
        "",
        "### Fix applied",
        fix.fix_applied,
        "",
        "### Incident details",
        f"- **Query ID:** `{query_id}`",
        f"- **dbt project:** `{pipeline.dbt_name}`",
    ]
    if start_time:
        lines.append(f"- **Failed at:** {start_time}")
    lines.extend(
        [
            "",
            "<details>",
            "<summary>Raw Snowflake error</summary>",
            "",
            "```",
            error.strip(),
            "```",
            "",
            "</details>",
            "",
            "<details>",
            "<summary>SQL diff</summary>",
            "",
            "```diff",
            diff,
            "```",
            "",
            "</details>",
        ]
    )
    return "\n".join(lines)


def _build_pr_title(fix: FixResult) -> str:
    return f"fix({fix.issue_type.lower()}): {fix.summary}"


def heal_with_rules(
    failure: dict[str, Any],
    pipeline: PipelineConfig | None = None,
) -> dict[str, Any] | None:
    error = failure.get("error_message", "")
    query_id = failure.get("query_id", "unknown")
    pipeline_id = failure.get("pipeline_id", "")
    if pipeline is None and pipeline_id:
        pipeline = get_pipeline(pipeline_id)

    if pipeline is None:
        from agent.pipeline_registry import list_pipelines

        enabled = list_pipelines(enabled_only=True)
        pipeline = enabled[0] if enabled else None
    if pipeline is None:
        log("rules", "No pipeline config available")
        return None

    log("rules", f"[{pipeline.pipeline_id}] Diagnosing query_id={query_id}")
    chat_log("assistant", f"Diagnosing failure for pipeline {pipeline.dbt_name}: {error[:200]}")

    sql = _get_model_sql(pipeline)
    columns = snowflake_tools.describe_table(
        "raw_sales",
        database=pipeline.snowflake_database,
        schema=pipeline.snowflake_schema,
    )

    fix = (
        _fix_schema_drift(sql, error, columns)
        or _fix_divide_by_zero(sql, error)
        or _fix_sql_syntax(sql, error)
    )
    if not fix:
        log("rules", f"No matching rule for query_id={query_id}")
        chat_log("assistant", f"No automatic fix rule matched for query_id={query_id}")
        return None

    log("rules", f"Matched rule: {fix.issue_type} — {fix.summary}")
    chat_log("assistant", f"Applying fix: {fix.summary}")

    branch = f"auto-heal/{query_id[:8]}"
    body = _build_pr_body(failure, fix, sql, pipeline)
    result = github_tools.create_fix_pr(
        branch_name=branch,
        file_path=pipeline.model_file_path,
        new_content=fix.new_sql,
        title=_build_pr_title(fix),
        body=body,
        incident_id=query_id,
        repo_name=pipeline.github_repo_slug,
    )
    record_pr_opened(query_id, result["pr_url"], result["pr_number"])
    log("rules", f"PR #{result.get('pr_number')} opened: {result.get('pr_url')}")
    chat_log("assistant", f"Opened PR #{result.get('pr_number')}: {result.get('pr_url')}")
    return result
