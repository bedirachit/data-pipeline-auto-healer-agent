"""End-to-end bootstrap: Snowflake schema, seed, dbt run, validate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.config import env, snowflake_connect_kwargs


def require_account() -> None:
    if not env("SNOWFLAKE_ACCOUNT"):
        raise SystemExit(
            "SNOWFLAKE_ACCOUNT is empty in .env.\n"
            "Set your Snowflake account identifier (e.g. VYFQEYS-NW10576)."
        )


def run(cmd: list[str]) -> None:
    print(f">> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def verify_snowflake_data() -> None:
    import snowflake.connector

    kwargs = snowflake_connect_kwargs()
    schema = kwargs["schema"]
    db = kwargs["database"]
    with snowflake.connector.connect(**kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {db}.{schema}.raw_sales")
            raw = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {db}.{schema}.sales_summary")
            summary = cur.fetchone()[0]
            print(f"Snowflake raw_sales: {raw} rows, sales_summary: {summary} rows")
            if raw == 0:
                raise SystemExit("raw_sales is empty — run seed_data.py")
            if summary == 0:
                raise SystemExit("sales_summary is empty — dbt run may have failed")


def main() -> None:
    require_account()
    run([sys.executable, str(ROOT / "pipeline/scripts/setup_snowflake.py")])
    run([sys.executable, str(ROOT / "pipeline/scripts/seed_data.py")])
    run([sys.executable, str(ROOT / "pipeline/scripts/run_pipeline.py"), "--expect", "success"])
    verify_snowflake_data()
    print("Setup complete — dbt pipeline validated.")


if __name__ == "__main__":
    main()
