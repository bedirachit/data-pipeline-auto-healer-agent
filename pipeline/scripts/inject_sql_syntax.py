"""Inject scenario 3: SQL syntax error (missing comma) in dbt model."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.scripts.inject_failure import patch_dbt_model

FAILING_MODEL = """-- demo_sales_etl
{{ config(
    materialized='table',
    tags=['demo_sales_etl']
) }}

select
    user_id
    sum(qty) as total_qty,
    max(sale_date) as last_sale
from {{ source('demo', 'raw_sales') }}
group by user_id
"""


def main() -> None:
    patch_dbt_model(FAILING_MODEL)
    print("SQL syntax error injected. Re-run dbt to trigger failure.")


if __name__ == "__main__":
    main()
