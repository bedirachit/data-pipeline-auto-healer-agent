"""Start/stop the agent watcher subprocess."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.config import AGENT_PID_FILE, PROJECT_ROOT

_meta_file = AGENT_PID_FILE.with_suffix(".meta")


def _read_meta() -> dict[str, str]:
    if not _meta_file.exists():
        return {}
    lines = _meta_file.read_text(encoding="utf-8").strip().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def _write_meta(started_at: str, rules_only: bool) -> None:
    _meta_file.write_text(
        f"started_at={started_at}\nrules_only={'true' if rules_only else 'false'}\n",
        encoding="utf-8",
    )


def _clear_meta() -> None:
    AGENT_PID_FILE.unlink(missing_ok=True)
    _meta_file.unlink(missing_ok=True)


def _is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_status() -> dict:
    if not AGENT_PID_FILE.exists():
        return {"running": False, "pid": None, "started_at": None, "rules_only": False}
    try:
        pid = int(AGENT_PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        _clear_meta()
        return {"running": False, "pid": None, "started_at": None, "rules_only": False}
    if not _is_running(pid):
        _clear_meta()
        return {"running": False, "pid": None, "started_at": None, "rules_only": False}
    meta = _read_meta()
    return {
        "running": True,
        "pid": pid,
        "started_at": meta.get("started_at"),
        "rules_only": meta.get("rules_only") == "true",
    }


def start_agent(rules_only: bool = True) -> dict:
    status = get_status()
    if status["running"]:
        return {"ok": False, "message": f"Agent already running (PID {status['pid']})", **status}

    cmd = [sys.executable, "-m", "agent.main", "watch-multi"]
    if rules_only:
        cmd.append("--rules-only")

    log_path = PROJECT_ROOT / "agent" / "audit" / "agent_process.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=0,
    )
    AGENT_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    _write_meta(datetime.now(timezone.utc).isoformat(), rules_only)
    time.sleep(0.5)
    return {"ok": True, "message": f"Agent started (PID {proc.pid})", "pid": proc.pid, "rules_only": rules_only}


def stop_agent() -> dict:
    status = get_status()
    if not status["running"]:
        _clear_meta()
        return {"ok": True, "message": "Agent was not running"}

    pid = status["pid"]
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False, capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            if _is_running(pid):
                os.kill(pid, signal.SIGKILL)
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    _clear_meta()
    return {"ok": True, "message": f"Agent stopped (PID {pid})"}
