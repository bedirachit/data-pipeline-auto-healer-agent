"""CLI entrypoint for the auto-healer agent."""

from __future__ import annotations

import argparse

from agent.agent_runner import heal_failure
from agent.logging_utils import log
from agent.multi_watcher import watch_multi
from agent.pipeline_registry import PipelineConfig, list_pipelines
from agent.tools import snowflake_tools
from agent.watcher import watch


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL Recovery Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("watch", help="Poll single pipeline (legacy env config)")
    sub.add_parser("watch-multi", help="Poll all registered pipelines")
    sub.add_parser("heal-once", help="Heal the most recent failure once")
    sub.add_parser("list-failures", help="List recent pipeline failures")

    args = parser.parse_args()

    if args.command == "list-failures":
        pipelines = list_pipelines(enabled_only=True)
        total = 0
        for p in pipelines:
            rows = snowflake_tools.get_recent_failures(minutes=120, limit=20, pipeline=p)
            log("list", f"[{p.pipeline_id}] {len(rows)} failure(s)")
            for row in rows:
                row["pipeline_id"] = p.pipeline_id
                print(row)
            total += len(rows)
        if not pipelines:
            rows = snowflake_tools.get_recent_failures(minutes=120, limit=20)
            for row in rows:
                print(row)
            total = len(rows)
        log("list", f"Total: {total} failure(s)")
        return

    def on_failure_legacy(row: dict) -> None:
        qid = row.get("query_id", "unknown")
        log("heal", f"Processing failure query_id={qid}")
        result = heal_failure(row, use_claude=True)
        if result and result.get("pr_url"):
            log("heal", f"PR opened: {result['pr_url']}")

    def on_failure_multi(row: dict, pipeline: PipelineConfig) -> None:
        qid = row.get("query_id", "unknown")
        log("heal", f"[{pipeline.pipeline_id}] Processing failure query_id={qid}")
        result = heal_failure(row, pipeline=pipeline, use_claude=True)
        if result and result.get("pr_url"):
            log("heal", f"PR opened: {result['pr_url']}")

    if args.command == "watch":
        log("main", "Legacy single-pipeline mode: claude (falls back to rules on error)")
        watch(on_failure_legacy)
    elif args.command == "watch-multi":
        log("main", "Multi-pipeline mode: claude (falls back to rules on error)")
        watch_multi(on_failure_multi)
    elif args.command == "heal-once":
        pipelines = list_pipelines(enabled_only=True)
        failures = []
        for p in pipelines:
            rows = snowflake_tools.get_recent_failures(minutes=120, limit=1, pipeline=p)
            if rows:
                rows[0]["pipeline_id"] = p.pipeline_id
                failures.append((rows[0], p))
        if not failures:
            log("heal", "No recent failures found")
            return
        failure, pipeline = failures[0]
        result = heal_failure(failure, pipeline=pipeline)
        print(result)


if __name__ == "__main__":
    main()
