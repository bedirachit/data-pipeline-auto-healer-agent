"""Pipeline registry backed by data/pipelines.csv."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import snowflake.connector
from github import Github

from agent.config import PIPELINES_CSV, env, require_env, snowflake_connect_kwargs
from agent.metrics_store import _read_csv, _write_csv, file_lock

PIPELINE_COLUMNS = [
    "pipeline_id",
    "dbt_name",
    "snowflake_database",
    "snowflake_schema",
    "github_repo_url",
    "model_file_path",
    "enabled",
    "created_at",
]

@dataclass
class PipelineConfig:
    pipeline_id: str
    dbt_name: str
    snowflake_database: str
    snowflake_schema: str
    github_repo_url: str
    model_file_path: str
    enabled: bool = True
    created_at: str = ""

    @property
    def dbt_project_object(self) -> str:
        return f"{self.snowflake_database}.{self.snowflake_schema}.{self.dbt_name}"

    @property
    def github_repo_slug(self) -> str:
        return parse_github_repo(self.github_repo_url)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_github_repo(url: str) -> str:
    """Return owner/repo from a GitHub URL or slug."""
    url = url.strip().rstrip("/")
    if url.startswith("http"):
        path = urlparse(url).path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    if "/" in url and " " not in url:
        return url
    raise ValueError(f"Invalid GitHub repo URL: {url}")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "pipeline"


def _empty_pipelines_df() -> pd.DataFrame:
    return pd.DataFrame(columns=PIPELINE_COLUMNS)


def _ensure_pipelines_file() -> None:
    if not PIPELINES_CSV.exists():
        seed = pd.DataFrame(
            [
                {
                    "pipeline_id": "snowflakes_sales",
                    "dbt_name": env("DBT_PROJECT_OBJECT", "DEMO_DB.DEMO_SCHEMA.SNOWFLAKES_SALES").split(".")[-1],
                    "snowflake_database": env("SNOWFLAKE_DATABASE", "DEMO_DB"),
                    "snowflake_schema": env("SNOWFLAKE_SCHEMA", "DEMO_SCHEMA"),
                    "github_repo_url": f"https://github.com/{env('GITHUB_REPO', 'bedirachit/snowflake-sales-aggregate-dbt')}",
                    "model_file_path": env("DBT_MODEL_GITHUB_PATH") or "pipeline/dbt/models/marts/sales_summary.sql",
                    "enabled": "true",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )
        _write_csv(PIPELINES_CSV, seed, PIPELINE_COLUMNS)


def list_pipelines(enabled_only: bool = False) -> list[PipelineConfig]:
    _ensure_pipelines_file()
    df = _read_csv(PIPELINES_CSV, PIPELINE_COLUMNS)
    pipelines = [_row_to_pipeline(row) for _, row in df.iterrows()]
    if enabled_only:
        pipelines = [p for p in pipelines if p.enabled]
    return pipelines


def get_pipeline(pipeline_id: str) -> PipelineConfig | None:
    for p in list_pipelines():
        if p.pipeline_id == pipeline_id:
            return p
    return None


def _row_to_pipeline(row: pd.Series) -> PipelineConfig:
    enabled_val = str(row.get("enabled", "true")).lower()
    return PipelineConfig(
        pipeline_id=str(row["pipeline_id"]),
        dbt_name=str(row["dbt_name"]),
        snowflake_database=str(row["snowflake_database"]),
        snowflake_schema=str(row["snowflake_schema"]),
        github_repo_url=str(row["github_repo_url"]),
        model_file_path=str(row["model_file_path"]),
        enabled=enabled_val in ("true", "1", "yes"),
        created_at=str(row.get("created_at", "")),
    )


def save_pipeline(
    dbt_name: str,
    snowflake_database: str,
    snowflake_schema: str,
    github_repo_url: str,
    model_file_path: str,
    pipeline_id: str | None = None,
    enabled: bool = True,
) -> PipelineConfig:
    _ensure_pipelines_file()
    pid = (pipeline_id or "").strip() or slugify(dbt_name)
    cfg = PipelineConfig(
        pipeline_id=pid,
        dbt_name=dbt_name.strip(),
        snowflake_database=snowflake_database.strip(),
        snowflake_schema=snowflake_schema.strip(),
        github_repo_url=github_repo_url.strip(),
        model_file_path=model_file_path.strip(),
        enabled=enabled,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with file_lock(PIPELINES_CSV):
        df = _read_csv(PIPELINES_CSV, PIPELINE_COLUMNS)
        df = df[df["pipeline_id"] != pid]
        df = pd.concat([df, pd.DataFrame([cfg.to_dict()])], ignore_index=True)
        _write_csv(PIPELINES_CSV, df, PIPELINE_COLUMNS)
    return cfg


def delete_pipeline(pipeline_id: str) -> bool:
    _ensure_pipelines_file()
    with file_lock(PIPELINES_CSV):
        df = _read_csv(PIPELINES_CSV, PIPELINE_COLUMNS)
        before = len(df)
        df = df[df["pipeline_id"] != pipeline_id]
        if len(df) == before:
            return False
        _write_csv(PIPELINES_CSV, df, PIPELINE_COLUMNS)
    return True


def test_connection(pipeline: PipelineConfig | dict[str, Any]) -> dict[str, Any]:
    """Verify Snowflake dbt project and GitHub repo exist."""
    if isinstance(pipeline, dict):
        pipeline = PipelineConfig(
            pipeline_id=pipeline.get("pipeline_id", "test"),
            dbt_name=pipeline["dbt_name"],
            snowflake_database=pipeline["snowflake_database"],
            snowflake_schema=pipeline["snowflake_schema"],
            github_repo_url=pipeline["github_repo_url"],
            model_file_path=pipeline["model_file_path"],
        )

    messages: list[str] = []
    snowflake_ok = False
    github_ok = False

    try:
        with snowflake.connector.connect(**snowflake_connect_kwargs()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SHOW DBT PROJECTS IN SCHEMA {pipeline.snowflake_database}.{pipeline.snowflake_schema}"
                )
                rows = cur.fetchall()
                names = {str(r[1]).upper() for r in rows} if rows else set()
                if pipeline.dbt_name.upper() in names:
                    snowflake_ok = True
                    messages.append(f"Snowflake: dbt project '{pipeline.dbt_name}' found.")
                else:
                    messages.append(
                        f"Snowflake: dbt project '{pipeline.dbt_name}' not found in "
                        f"{pipeline.snowflake_database}.{pipeline.snowflake_schema}."
                    )
    except Exception as exc:
        messages.append(f"Snowflake error: {exc}")

    try:
        repo_slug = parse_github_repo(pipeline.github_repo_url)
        token = require_env("GITHUB_TOKEN")
        gh = Github(token)
        repo = gh.get_repo(repo_slug)
        github_ok = True
        messages.append(f"GitHub: repo '{repo.full_name}' accessible.")
        try:
            repo.get_contents(pipeline.model_file_path, ref="main")
            messages.append(f"GitHub: model file '{pipeline.model_file_path}' found on main.")
        except Exception as exc:
            messages.append(f"GitHub: model file check warning — {exc}")
    except Exception as exc:
        messages.append(f"GitHub error: {exc}")

    return {
        "snowflake_ok": snowflake_ok,
        "github_ok": github_ok,
        "ok": snowflake_ok and github_ok,
        "messages": messages,
    }
