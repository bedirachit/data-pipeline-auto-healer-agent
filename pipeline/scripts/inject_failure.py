"""Shared failure injection helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import snowflake.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.config import DBT_MODEL, PROJECT_ROOT, snowflake_connect_kwargs, sql_path


def run_sql_file(path: Path) -> None:
    kwargs = snowflake_connect_kwargs()
    statements = path.read_text(encoding="utf-8").split(";")
    with snowflake.connector.connect(**kwargs) as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cleaned = stmt.strip()
                if cleaned and not cleaned.startswith("--"):
                    cur.execute(cleaned)
                    print(f"Executed: {cleaned[:80]}...")


def patch_dbt_model(content: str) -> None:
    DBT_MODEL.write_text(content, encoding="utf-8")
    print(f"Patched {DBT_MODEL}")
