"""Multi-pipeline watcher — polls all registered dbt projects."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from agent.config import env
from agent.logging_utils import log
from agent.metrics_store import record_failure
from agent.pipeline_registry import PipelineConfig, list_pipelines
from agent.tools import snowflake_tools

_seen: set[tuple[str, str]] = set()


def _error_summary(row: dict) -> str:
    msg = str(row.get("error_message", ""))
    for line in msg.splitlines():
        line = line.strip()
        if line and ("error" in line.lower() or "invalid" in line.lower()):
            return line[:120]
    return msg[:120] if msg else "unknown error"


def poll_once(
    on_failure: Callable[[dict, PipelineConfig], None],
    since: datetime,
) -> int:
    pipelines = list_pipelines(enabled_only=True)
    if not pipelines:
        log("watch", "No enabled pipelines in registry — add pipelines via dashboard")
        return 0

    new_count = 0
    for pipeline in pipelines:
        failures = snowflake_tools.get_recent_failures(
            minutes=60, limit=20, since=since, pipeline=pipeline
        )
        for row in failures:
            qid = str(row.get("query_id", ""))
            key = (pipeline.pipeline_id, qid)
            if not qid or key in _seen:
                continue
            _seen.add(key)
            new_count += 1
            row["pipeline_id"] = pipeline.pipeline_id
            row["dbt_name"] = pipeline.dbt_name
            log(
                "detect",
                f"[{pipeline.pipeline_id}] New failure query_id={qid} — {_error_summary(row)}",
            )
            record_failure(qid, pipeline.pipeline_id, _error_summary(row))
            on_failure(row, pipeline)
    return new_count


def watch_multi(
    on_failure: Callable[[dict, PipelineConfig], None],
    interval_sec: int | None = None,
) -> None:
    interval = interval_sec or int(env("AGENT_POLL_INTERVAL_SEC", "30"))
    started_at = datetime.now(timezone.utc)
    pipelines = list_pipelines(enabled_only=True)

    historical = 0
    for pipeline in pipelines:
        rows = snowflake_tools.get_recent_failures(minutes=120, limit=50, pipeline=pipeline)
        for row in rows:
            qid = str(row.get("query_id", ""))
            if qid:
                _seen.add((pipeline.pipeline_id, qid))
                historical += 1

    log("watch", f"Multi-pipeline watch started — {len(pipelines)} pipeline(s), poll every {interval}s")
    log("watch", f"Ignoring {historical} historical failure(s) from before agent start")
    log("watch", f"Only failures after {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')} will trigger healing")

    while True:
        try:
            count = poll_once(on_failure, since=started_at)
            if count:
                log("watch", f"Handled {count} new failure(s) this cycle")
        except Exception as exc:
            log("error", f"Poll failed: {exc}")
        time.sleep(interval)
