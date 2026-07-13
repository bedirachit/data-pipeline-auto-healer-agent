"""dbt CLI helpers for the auto-healer agent."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.config import DBT_MODEL_SELECT, DBT_PROJECT_OBJECT, env
from agent.tools import snowflake_tools
from pipeline.config import DBT_PROJECT_DIR, dbt_env


def execute_dbt_project(args: str | None = None) -> dict:
    """Re-run the deployed Snowflake dbt project after a fix is merged."""
    select = env("DBT_MODEL_SELECT", DBT_MODEL_SELECT)
    default_args = f"run --select {select} --target dev"
    return snowflake_tools.execute_dbt_project(args or default_args)


def run_dbt_model(select: str = DBT_MODEL_SELECT) -> dict:
    """Run dbt locally via CLI (dev fallback). Prefer execute_dbt_project for Snowflake deploy."""
    result = subprocess.run(
        ["dbt", "run", "--select", select],
        cwd=DBT_PROJECT_DIR,
        env=dbt_env(),
        capture_output=True,
        text=True,
    )
    return {
        "select": select,
        "returncode": result.returncode,
        "success": result.returncode == 0,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
    }


def get_dbt_run_logs(query_id: str | None = None) -> str:
    """Return recent dbt run output (native Snowflake log or local run_results)."""
    if query_id:
        try:
            log = snowflake_tools.get_dbt_log(query_id)
            if log:
                return log[-8000:]
        except Exception as exc:
            parts = [f"SYSTEM$GET_DBT_LOG failed: {exc}"]
        else:
            parts = []
    else:
        parts = []

    results_path = DBT_PROJECT_DIR / "target" / "run_results.json"
    if results_path.exists():
        data = json.loads(results_path.read_text(encoding="utf-8"))
        for r in data.get("results", []):
            parts.append(
                f"model={r.get('unique_id')} status={r.get('status')} "
                f"message={r.get('message', '')}"
            )

    log_path = DBT_PROJECT_DIR / "logs" / "dbt.log"
    if log_path.exists():
        parts.append("--- dbt.log tail ---")
        parts.append(log_path.read_text(encoding="utf-8", errors="ignore")[-6000:])

    return "\n".join(parts) if parts else "No dbt run results found. Run dbt first."
