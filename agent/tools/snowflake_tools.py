"""Snowflake query and schema tools for the auto-healer agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import snowflake.connector

from agent.config import env, snowflake_connect_kwargs, DBT_PROJECT_OBJECT
from agent.pipeline_registry import PipelineConfig


def _connect():
    return snowflake.connector.connect(**snowflake_connect_kwargs())


def _parts_from_pipeline(
    pipeline: PipelineConfig | None = None,
    database: str | None = None,
    schema: str | None = None,
    dbt_name: str | None = None,
) -> tuple[str, str, str]:
    if pipeline:
        return pipeline.snowflake_database, pipeline.snowflake_schema, pipeline.dbt_name
    if database and schema and dbt_name:
        return database, schema, dbt_name
    fq = env("DBT_PROJECT_OBJECT", DBT_PROJECT_OBJECT)
    parts = fq.split(".")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    db = env("SNOWFLAKE_DATABASE", "DEMO_DB")
    sch = env("SNOWFLAKE_SCHEMA", "DEMO_SCHEMA")
    return db, sch, fq


def get_recent_failures(
    minutes: int = 30,
    limit: int = 10,
    since: datetime | None = None,
    pipeline: PipelineConfig | None = None,
    database: str | None = None,
    schema: str | None = None,
    dbt_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return recent failed dbt runs for a pipeline."""
    db, sch, project = _parts_from_pipeline(pipeline, database, schema, dbt_name)
    rows = _get_dbt_project_failures(db, sch, project, minutes=minutes, limit=limit, since=since)
    if rows:
        return rows
    return _get_query_history_failures(
        project, minutes=minutes, limit=limit, since=since, database=db, schema=sch
    )


def _get_dbt_project_failures(
    database: str,
    schema: str,
    project: str,
    minutes: int = 30,
    limit: int = 10,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    since_clause = "AND query_start_time > %(since)s" if since else ""
    sql = f"""
    SELECT
        query_id,
        command AS query_text,
        error_message,
        query_start_time AS start_time,
        state,
        object_name
    FROM TABLE(SNOWFLAKE.INFORMATION_SCHEMA.DBT_PROJECT_EXECUTION_HISTORY(
        DATABASE => %(database)s,
        SCHEMA => %(schema)s,
        OBJECT_NAME => %(project)s,
        START_TIME_RANGE_START => DATEADD('minute', -%(minutes)s, CURRENT_TIMESTAMP()),
        RESULT_LIMIT => %(limit)s
    ))
    WHERE state IN ('HANDLED_ERROR', 'UNHANDLED_ERROR')
      AND error_message IS NOT NULL
      {since_clause}
    ORDER BY query_start_time DESC
    """
    params: dict[str, Any] = {
        "database": database,
        "schema": schema,
        "project": project,
        "minutes": minutes,
        "limit": limit,
    }
    if since:
        params["since"] = since
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_last_success(
    pipeline: PipelineConfig,
    after: datetime,
) -> dict[str, Any] | None:
    """Latest successful dbt run for pipeline after a given time."""
    sql = """
    SELECT query_id, query_end_time, state
    FROM TABLE(SNOWFLAKE.INFORMATION_SCHEMA.DBT_PROJECT_EXECUTION_HISTORY(
        DATABASE => %(database)s,
        SCHEMA => %(schema)s,
        OBJECT_NAME => %(project)s,
        START_TIME_RANGE_START => %(after)s,
        RESULT_LIMIT => 50
    ))
    WHERE state = 'SUCCESS'
    ORDER BY query_end_time DESC
    LIMIT 1
    """
    params = {
        "database": pipeline.snowflake_database,
        "schema": pipeline.snowflake_schema,
        "project": pipeline.dbt_name,
        "after": after,
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0].lower() for d in cur.description]
            return dict(zip(cols, row))


def has_failure_after(
    pipeline: PipelineConfig,
    after: datetime,
) -> bool:
    """True if pipeline had a failure after the given time."""
    rows = get_recent_failures(
        minutes=60 * 24 * 7,
        limit=5,
        since=after,
        pipeline=pipeline,
    )
    return len(rows) > 0


def _get_query_history_failures(
    project: str,
    minutes: int = 30,
    limit: int = 10,
    since: datetime | None = None,
    database: str | None = None,
    schema: str | None = None,
) -> list[dict[str, Any]]:
    tag = env("AGENT_DEMO_TAG", "demo_sales_etl")
    model = env("DBT_MODEL_SELECT", "sales_summary")
    since_clause = "AND start_time > %(since)s" if since else ""
    sql = f"""
    SELECT query_id, query_text, error_message, start_time
    FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
        END_TIME_RANGE_START => DATEADD('minute', -%(minutes)s, CURRENT_TIMESTAMP()),
        END_TIME_RANGE_END => CURRENT_TIMESTAMP(),
        RESULT_LIMIT => %(limit)s
    ))
    WHERE execution_status = 'FAIL'
      AND (
        query_text ILIKE %(tag_pattern)s
        OR query_text ILIKE %(model_pattern)s
        OR query_text ILIKE %(execute_dbt_pattern)s
        OR query_text ILIKE %(project_pattern)s
      )
      {since_clause}
    ORDER BY start_time DESC
    """
    params: dict[str, Any] = {
        "minutes": minutes,
        "limit": limit,
        "tag_pattern": f"%{tag}%",
        "model_pattern": f"%{model}%",
        "execute_dbt_pattern": "%EXECUTE DBT PROJECT%",
        "project_pattern": f"%{project.lower()}%",
    }
    if since:
        params["since"] = since
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_dbt_log(query_id: str) -> str:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT SYSTEM$GET_DBT_LOG(%(qid)s)", {"qid": query_id})
            row = cur.fetchone()
            return row[0] if row else ""


def describe_table(
    table_name: str,
    database: str | None = None,
    schema: str | None = None,
) -> list[dict[str, str]]:
    sch = schema or env("SNOWFLAKE_SCHEMA", "DEMO_SCHEMA")
    db = database or env("SNOWFLAKE_DATABASE", "DEMO_DB")
    fq = table_name if "." in table_name else f"{db}.{sch}.{table_name}"

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DESC TABLE {fq}")
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_lineage(
    table_name: str,
    database: str | None = None,
    schema: str | None = None,
    model_path: str = "pipeline/dbt/models/marts/sales_summary.sql",
) -> dict[str, Any]:
    sch = schema or env("SNOWFLAKE_SCHEMA", "DEMO_SCHEMA")
    db = database or env("SNOWFLAKE_DATABASE", "DEMO_DB")
    fq = table_name if "." in table_name else f"{db}.{sch}.{table_name}"

    fallback = {
        "object": fq,
        "upstream": [f"{db}.{sch}.raw_sales"],
        "downstream": [f"{db}.{sch}.sales_summary"],
        "dbt_model": model_path,
        "note": "Static demo lineage when GET_LINEAGE unavailable",
    }
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM TABLE(SNOWFLAKE.CORE.GET_LINEAGE('{fq}', 'TABLE', 'UPSTREAM'))"
                )
                rows = cur.fetchall()
                if rows:
                    return {"object": fq, "upstream_rows": rows}
    except Exception as exc:
        fallback["get_lineage_error"] = str(exc)
    return fallback
