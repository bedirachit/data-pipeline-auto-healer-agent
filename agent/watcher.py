"""Poll Snowflake for pipeline failures and trigger healing."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from agent.config import env
from agent.logging_utils import log
from agent.tools import snowflake_tools

_seen: set[str] = set()


def _error_summary(row: dict) -> str:
    """First error line from a Snowflake failure row, truncated for logs."""
    msg = str(row.get("error_message", ""))
    for line in msg.splitlines():
        line = line.strip()
        if line and ("error" in line.lower() or "invalid" in line.lower()):
            return line[:120]
    return msg[:120] if msg else "unknown error"


def poll_once(on_failure: Callable[[dict], None], since: datetime) -> int:
    """Handle failures newer than ``since``. Returns how many were new."""
    failures = snowflake_tools.get_recent_failures(minutes=60, limit=20, since=since)
    new_count = 0
    for row in failures:
        qid = str(row.get("query_id", ""))
        if not qid or qid in _seen:
            continue
        _seen.add(qid)
        new_count += 1
        log("detect", f"New failure query_id={qid} — {_error_summary(row)}")
        on_failure(row)
    return new_count


def watch(on_failure: Callable[[dict], None], interval_sec: int | None = None) -> None:
    """Poll the env-configured dbt project until the process is stopped.

    Failures already in history are marked seen so a restart does not reopen
    pull requests for old incidents.
    """
    interval = interval_sec or int(env("AGENT_POLL_INTERVAL_SEC", "30"))
    started_at = datetime.now(timezone.utc)
    project = env("DBT_PROJECT_OBJECT")

    historical = snowflake_tools.get_recent_failures(minutes=120, limit=50)
    skipped = len(historical)
    for row in historical:
        qid = str(row.get("query_id", ""))
        if qid:
            _seen.add(qid)

    log("watch", f"Started — project={project}, poll every {interval}s")
    log("watch", f"Ignoring {skipped} historical failure(s) from before agent start")
    log("watch", f"Only failures after {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')} will trigger healing")

    while True:
        try:
            count = poll_once(on_failure, since=started_at)
            if count:
                log("watch", f"Handled {count} new failure(s) this cycle")
        except Exception as exc:
            log("error", f"Poll failed: {exc}")
        time.sleep(interval)
