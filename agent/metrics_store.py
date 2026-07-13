"""CSV-backed incident metrics store for the dashboard."""

from __future__ import annotations

import contextlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from agent.config import INCIDENTS_CSV

INCIDENT_COLUMNS = [
    "incident_id",
    "pipeline_id",
    "detected_at",
    "error_summary",
    "status",
    "pr_url",
    "pr_number",
    "pr_opened_at",
    "time_to_pr_sec",
    "time_to_fix_sec",
    "deploy_status",
    "last_success_at",
    "resolved_at",
]


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 10.0):
    """Simple lock file for CSV read/write."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(0.05)
    else:
        raise TimeoutError(f"Could not acquire lock for {path}")
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock_path.unlink()


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns]


def _write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df[columns].to_csv(path, index=False)


def _ensure_incidents_file() -> None:
    if not INCIDENTS_CSV.exists():
        _write_csv(INCIDENTS_CSV, pd.DataFrame(columns=INCIDENT_COLUMNS), INCIDENT_COLUMNS)


def list_incidents(pipeline_id: str | None = None) -> list[dict[str, Any]]:
    _ensure_incidents_file()
    df = _read_csv(INCIDENTS_CSV, INCIDENT_COLUMNS)
    if pipeline_id:
        df = df[df["pipeline_id"] == pipeline_id]
    return df.to_dict(orient="records")


def get_incident(incident_id: str) -> dict[str, Any] | None:
    for row in list_incidents():
        if row.get("incident_id") == incident_id:
            return row
    return None


def record_failure(
    incident_id: str,
    pipeline_id: str,
    error_summary: str,
    detected_at: datetime | None = None,
) -> dict[str, Any]:
    _ensure_incidents_file()
    if get_incident(incident_id):
        return get_incident(incident_id)  # type: ignore[return-value]

    ts = (detected_at or datetime.now(timezone.utc)).isoformat()
    row = {
        "incident_id": incident_id,
        "pipeline_id": pipeline_id,
        "detected_at": ts,
        "error_summary": error_summary[:500],
        "status": "open",
        "pr_url": "",
        "pr_number": "",
        "pr_opened_at": "",
        "time_to_pr_sec": "",
        "time_to_fix_sec": "",
        "deploy_status": "pending",
        "last_success_at": "",
        "resolved_at": "",
    }
    with file_lock(INCIDENTS_CSV):
        df = _read_csv(INCIDENTS_CSV, INCIDENT_COLUMNS)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        _write_csv(INCIDENTS_CSV, df, INCIDENT_COLUMNS)
    return row


def record_pr_opened(
    incident_id: str,
    pr_url: str,
    pr_number: int | str,
    pr_opened_at: datetime | None = None,
) -> None:
    _ensure_incidents_file()
    opened = pr_opened_at or datetime.now(timezone.utc)
    with file_lock(INCIDENTS_CSV):
        df = _read_csv(INCIDENTS_CSV, INCIDENT_COLUMNS)
        mask = df["incident_id"] == incident_id
        if not mask.any():
            return
        idx = df.index[mask][0]
        detected_raw = df.at[idx, "detected_at"]
        try:
            detected = datetime.fromisoformat(str(detected_raw))
            if detected.tzinfo is None:
                detected = detected.replace(tzinfo=timezone.utc)
            ttp = int((opened - detected).total_seconds())
        except Exception:
            ttp = ""
        df.at[idx, "status"] = "pr_opened"
        df.at[idx, "pr_url"] = pr_url
        df.at[idx, "pr_number"] = str(pr_number)
        df.at[idx, "pr_opened_at"] = opened.isoformat()
        df.at[idx, "time_to_pr_sec"] = str(ttp)
        df.at[idx, "deploy_status"] = "pending"
        _write_csv(INCIDENTS_CSV, df, INCIDENT_COLUMNS)


def update_deploy_status(
    incident_id: str,
    deploy_status: str,
    last_success_at: str = "",
    resolved_at: str = "",
    status: str | None = None,
    time_to_fix_sec: str = "",
) -> None:
    _ensure_incidents_file()
    with file_lock(INCIDENTS_CSV):
        df = _read_csv(INCIDENTS_CSV, INCIDENT_COLUMNS)
        mask = df["incident_id"] == incident_id
        if not mask.any():
            return
        idx = df.index[mask][0]
        df.at[idx, "deploy_status"] = deploy_status
        if last_success_at:
            df.at[idx, "last_success_at"] = last_success_at
        if resolved_at:
            df.at[idx, "resolved_at"] = resolved_at
        if status:
            df.at[idx, "status"] = status
        if time_to_fix_sec:
            df.at[idx, "time_to_fix_sec"] = time_to_fix_sec
        _write_csv(INCIDENTS_CSV, df, INCIDENT_COLUMNS)


def dashboard_kpis() -> dict[str, Any]:
    incidents = list_incidents()
    open_count = sum(1 for i in incidents if i.get("status") == "open")
    pr_count = sum(1 for i in incidents if i.get("pr_url"))
    deployed = sum(
        1 for i in incidents if i.get("status") == "deployed" and i.get("deploy_status") == "green"
    )
    ttp_vals = []
    for i in incidents:
        v = i.get("time_to_pr_sec", "")
        if v and str(v).isdigit():
            ttp_vals.append(int(v))
    avg_ttp = int(sum(ttp_vals) / len(ttp_vals)) if ttp_vals else 0
    return {
        "open_failures": open_count,
        "prs_opened": pr_count,
        "deployed_fixes": deployed,
        "avg_time_to_pr_sec": avg_ttp,
    }
