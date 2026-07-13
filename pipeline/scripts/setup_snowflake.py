"""Create Snowflake demo schema and tables."""

from __future__ import annotations

import sys
from pathlib import Path

import snowflake.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.config import PROJECT_ROOT, snowflake_connect_kwargs, sql_path


def run_sql_file(cursor, path: Path) -> None:
    statements = path.read_text(encoding="utf-8").split(";")
    for stmt in statements:
        cleaned = stmt.strip()
        if cleaned:
            cursor.execute(cleaned)


def main() -> None:
    ddl = sql_path("ddl", "01_create_schema.sql")
    kwargs = snowflake_connect_kwargs()
    print(f"Connecting to Snowflake account {kwargs['account']}...")
    with snowflake.connector.connect(**kwargs) as conn:
        with conn.cursor() as cur:
            run_sql_file(cur, ddl)
            print("Schema and tables created.")
    print("Done. Run seed_data.py next.")


if __name__ == "__main__":
    main()
