"""Verify deployed fixes via Snowflake execution history."""

from __future__ import annotations

from datetime import datetime, timezone

from agent.logging_utils import log
from agent.metrics_store import list_incidents, update_deploy_status
from agent.pipeline_registry import get_pipeline
from agent.tools import snowflake_tools


def refresh_deploy_status() -> int:
    """Update deploy_status for incidents with open PRs. Returns count updated."""
    updated = 0
    incidents = list_incidents()
    for inc in incidents:
        if inc.get("status") not in ("pr_opened", "open"):
            continue
        if inc.get("status") == "deployed" and inc.get("deploy_status") == "green":
            continue

        pipeline = get_pipeline(str(inc.get("pipeline_id", "")))
        if not pipeline:
            continue

        incident_id = str(inc["incident_id"])
        detected_raw = inc.get("detected_at", "")
        try:
            detected = datetime.fromisoformat(detected_raw)
            if detected.tzinfo is None:
                detected = detected.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        try:
            success = snowflake_tools.get_last_success(pipeline, after=detected)
        except Exception as exc:
            log("deploy", f"[{pipeline.pipeline_id}] incident {incident_id[:8]} — check skipped: {exc}")
            continue

        if success:
            end_time = success.get("query_end_time")
            if isinstance(end_time, datetime):
                resolved = end_time
                if resolved.tzinfo is None:
                    resolved = resolved.replace(tzinfo=timezone.utc)
                else:
                    resolved = resolved.astimezone(timezone.utc)
            elif end_time:
                resolved = datetime.fromisoformat(str(end_time).replace("Z", "+00:00"))
                if resolved.tzinfo is None:
                    resolved = resolved.replace(tzinfo=timezone.utc)
                else:
                    resolved = resolved.astimezone(timezone.utc)
            else:
                resolved = datetime.now(timezone.utc)
            end_iso = resolved.isoformat()
            try:
                ttf = int((resolved - detected).total_seconds())
            except Exception:
                ttf = ""
            update_deploy_status(
                incident_id,
                deploy_status="green",
                last_success_at=end_iso,
                resolved_at=end_iso,
                status="deployed",
                time_to_fix_sec=str(ttf),
            )
            log("deploy", f"[{pipeline.pipeline_id}] incident {incident_id[:8]} — deployed (green)")
            updated += 1
            continue

        if inc.get("status") == "pr_opened":
            try:
                still_failing = snowflake_tools.has_failure_after(pipeline, after=detected)
            except Exception as exc:
                log("deploy", f"[{pipeline.pipeline_id}] incident {incident_id[:8]} — failure check skipped: {exc}")
                continue
            if still_failing and inc.get("pr_opened_at"):
                update_deploy_status(incident_id, deploy_status="red", status="failed")
                log("deploy", f"[{pipeline.pipeline_id}] incident {incident_id[:8]} — still failing (red)")
                updated += 1

    return updated
