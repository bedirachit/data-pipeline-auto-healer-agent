"""Inject scenario 1: schema drift (rename qty -> quantity)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.config import sql_path
from pipeline.scripts.inject_failure import run_sql_file


def main() -> None:
    run_sql_file(sql_path("scenarios", "inject_schema_drift.sql"))
    print("Schema drift injected. Re-run pipeline to trigger failure.")


if __name__ == "__main__":
    main()
