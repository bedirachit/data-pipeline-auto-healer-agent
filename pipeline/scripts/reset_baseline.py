"""Reset demo schema to baseline (qty column, clean dbt model)."""

from __future__ import annotations

import sys
from pathlib import Path

import snowflake.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.config import DBT_MODEL, PROJECT_ROOT, snowflake_connect_kwargs

BASELINE_MODEL = """-- demo_sales_etl
{{ config(
    materialized='table',
    tags=['demo_sales_etl']
) }}

select
    user_id,
    sum(qty) as total_qty,
    max(sale_date) as last_sale
from {{ source('demo', 'raw_sales') }}
group by user_id
"""


def reset_dbt_model() -> None:
    DBT_MODEL.write_text(BASELINE_MODEL, encoding="utf-8")
    print(f"Reset {DBT_MODEL.name} to baseline.")


def reset_schema(cursor, schema: str) -> None:
    cursor.execute(f"ALTER TABLE {schema}.raw_sales RENAME COLUMN quantity TO qty")
    print("Renamed quantity -> qty (if needed).")


def main() -> None:
    kwargs = snowflake_connect_kwargs()
    schema = kwargs["schema"]
    db = kwargs["database"]
    reset_dbt_model()

    try:
        with snowflake.connector.connect(**kwargs) as conn:
            with conn.cursor() as cur:
                try:
                    reset_schema(cur, schema)
                except Exception:
                    print("Column already named qty (OK).")
                cur.execute(f"DROP TABLE IF EXISTS {db}.{schema}.sales_summary")
                print("Dropped sales_summary (dbt will rebuild).")
    except Exception as exc:
        print(f"Snowflake reset skipped: {exc}")

    seed_script = Path(__file__).parent / "seed_data.py"
    import subprocess

    subprocess.run([sys.executable, str(seed_script)], check=False)
    print("Baseline reset complete.")


if __name__ == "__main__":
    main()
