"""GitHub PR creation and file fetch for pipeline fixes."""

from __future__ import annotations

import base64
from typing import Any

from github import Github

from agent.config import PROJECT_ROOT, env, require_env


def fetch_file_content(repo_name: str, file_path: str, ref: str = "main") -> str:
    """Read a file from a GitHub repo."""
    token = require_env("GITHUB_TOKEN")
    gh = Github(token)
    repo = gh.get_repo(repo_name)
    content_file = repo.get_contents(file_path.replace("\\", "/"), ref=ref)
    raw = content_file.content
    if content_file.encoding == "base64":
        return base64.b64decode(raw).decode("utf-8")
    return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)


def create_fix_pr(
    branch_name: str,
    file_path: str,
    new_content: str,
    title: str,
    body: str,
    incident_id: str,
    repo_name: str | None = None,
) -> dict[str, Any]:
    """Create branch, commit file change, and open pull request."""
    if not branch_name.startswith("auto-heal/"):
        raise ValueError("Branch must start with auto-heal/")

    token = require_env("GITHUB_TOKEN")
    repo_name = repo_name or env("GITHUB_REPO", "bedirachit/snowflake-sales-aggregate-dbt")
    gh = Github(token)
    repo = gh.get_repo(repo_name)

    rel_path = file_path.replace("\\", "/")
    if rel_path.startswith(str(PROJECT_ROOT).replace("\\", "/")):
        rel_path = rel_path[len(str(PROJECT_ROOT).replace("\\", "/")) + 1 :]

    main = repo.get_branch("main")
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main.commit.sha)

    try:
        content_file = repo.get_contents(rel_path, ref=branch_name)
        repo.update_file(
            rel_path,
            f"auto-heal: {incident_id}",
            new_content,
            content_file.sha,
            branch=branch_name,
        )
    except Exception:
        repo.create_file(
            rel_path,
            f"auto-heal: {incident_id}",
            new_content,
            branch=branch_name,
        )

    pr = repo.create_pull(title=title, body=body, head=branch_name, base="main")
    return {
        "pr_number": pr.number,
        "pr_url": pr.html_url,
        "branch": branch_name,
        "file": rel_path,
    }
