"""Load seed data via INSERT (Windows-friendly, no stage required)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import snowflake.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.config import data_path, snowflake_connect_kwargs


def insert_csv(cursor, table: str, csv_file: Path) -> None:
    cursor.execute(f"TRUNCATE TABLE IF EXISTS {table}")
    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    for row in rows:
        cursor.execute(sql, [row[c] for c in cols])


def main() -> None:
    kwargs = snowflake_connect_kwargs()
    schema = kwargs["schema"]

    with snowflake.connector.connect(**kwargs) as conn:
        with conn.cursor() as cur:
            insert_csv(cur, f"{schema}.raw_sales", data_path("raw_sales.csv"))
            insert_csv(cur, f"{schema}.dim_product", data_path("dim_product.csv"))
            cur.execute(f"SELECT COUNT(*) FROM {schema}.raw_sales")
            raw_count = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {schema}.dim_product")
            dim_count = cur.fetchone()[0]
            print(f"Loaded raw_sales: {raw_count} rows, dim_product: {dim_count} rows")


if __name__ == "__main__":
    main()
