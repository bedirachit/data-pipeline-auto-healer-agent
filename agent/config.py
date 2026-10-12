"""Agent configuration loaded from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

AUDIT_DIR = PROJECT_ROOT / "agent" / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG = AUDIT_DIR / "incidents.jsonl"
CHAT_LOG = AUDIT_DIR / "agent_chat.log"

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PIPELINES_CSV = DATA_DIR / "pipelines.csv"
INCIDENTS_CSV = DATA_DIR / "incidents.csv"
AGENT_PID_FILE = DATA_DIR / "agent.pid"

DBT_MODEL = PROJECT_ROOT / "pipeline" / "dbt" / "models" / "marts" / "sales_summary.sql"
DBT_MODEL_SELECT = "sales_summary"


def env(key: str, default: str = "") -> str:
    """Return an environment variable, or ``default`` when it is unset."""
    return os.getenv(key, default)


DBT_MODEL_GITHUB_PATH = env("DBT_MODEL_GITHUB_PATH") or "pipeline/dbt/models/marts/sales_summary.sql"
DBT_PROJECT_OBJECT = env("DBT_PROJECT_OBJECT", "DEMO_DB.DEMO_SCHEMA.SNOWFLAKES_SALES")


def require_env(key: str) -> str:
    """Return an environment variable or raise if it is missing or empty."""
    value = env(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def snowflake_connect_kwargs() -> dict:
    """Connection kwargs for ``snowflake.connector.connect``."""
    return {
        "account": require_env("SNOWFLAKE_ACCOUNT"),
        "user": env("SNOWFLAKE_USER"),
        "password": require_env("SNOWFLAKE_PASSWORD"),
        "warehouse": env("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        "role": env("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        "database": env("SNOWFLAKE_DATABASE", "DEMO_DB"),
        "schema": env("SNOWFLAKE_SCHEMA", "DEMO_SCHEMA"),
    }
