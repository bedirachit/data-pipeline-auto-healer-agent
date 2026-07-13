"""Repository file read/search helpers."""

from __future__ import annotations

import re
from pathlib import Path

from agent.config import DBT_MODEL, PROJECT_ROOT


def read_pipeline_sql(path: str = "") -> str:
    """Read dbt model SQL or another pipeline file."""
    if not path:
        target = DBT_MODEL
    else:
        target = Path(path)
        if not target.is_absolute():
            target = PROJECT_ROOT / path
    return target.read_text(encoding="utf-8")


def search_repo(pattern: str, subdir: str = "pipeline") -> list[dict[str, str]]:
    """Search pipeline code for a regex pattern."""
    root = PROJECT_ROOT / subdir
    results: list[dict[str, str]] = []
    regex = re.compile(pattern, re.IGNORECASE)
    for path in root.rglob("*"):
        if path.suffix not in {".py", ".sql", ".yml", ".yaml"}:
            continue
        if "target" in path.parts or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                results.append(
                    {
                        "file": str(path.relative_to(PROJECT_ROOT)),
                        "line": str(i),
                        "text": line.strip(),
                    }
                )
    return results[:50]
