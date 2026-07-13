"""Run dbt models against Snowflake."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.config import DBT_MODEL_SELECT, DBT_PROJECT_DIR, dbt_env


def run_dbt(select: str = DBT_MODEL_SELECT) -> subprocess.CompletedProcess[str]:
    cmd = ["dbt", "run", "--select", select]
    print(f">> {' '.join(cmd)} (cwd={DBT_PROJECT_DIR})")
    return subprocess.run(
        cmd,
        cwd=DBT_PROJECT_DIR,
        env=dbt_env(),
        capture_output=True,
        text=True,
    )


def last_run_failed() -> bool:
    results_path = DBT_PROJECT_DIR / "target" / "run_results.json"
    if not results_path.exists():
        return False
    data = json.loads(results_path.read_text(encoding="utf-8"))
    for result in data.get("results", []):
        if result.get("status") in ("error", "fail"):
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dbt pipeline")
    parser.add_argument("--select", default=DBT_MODEL_SELECT)
    parser.add_argument("--expect", choices=["success", "failed"], default="success")
    args = parser.parse_args()

    result = run_dbt(args.select)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    succeeded = result.returncode == 0
    if args.expect == "success" and not succeeded:
        raise SystemExit(f"dbt run failed (exit {result.returncode})")
    if args.expect == "failed" and succeeded:
        raise SystemExit("Expected dbt failure but run succeeded")
    print(f"dbt run finished: {'success' if succeeded else 'failed'}")


if __name__ == "__main__":
    main()
