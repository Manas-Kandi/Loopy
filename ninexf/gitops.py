"""Thin git wrapper via subprocess. The git history is the primary research artifact."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


def _git(project_dir: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def init_repo(project_dir: Path) -> None:
    _git(project_dir, "init", "-q")
    # Identity local to this repo so runs work on machines without global config.
    _git(project_dir, "config", "user.name", "9xf-loop-agent")
    _git(project_dir, "config", "user.email", "agent@9xf.local")


def commit_all(project_dir: Path, message: str, allow_empty: bool = False) -> str:
    """Stage everything and commit. Returns the short hash."""
    _git(project_dir, "add", "-A")
    args = ["commit", "-q", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    _git(project_dir, *args)
    return _git(project_dir, "rev-parse", "--short", "HEAD").strip()


def has_changes(project_dir: Path) -> bool:
    return bool(_git(project_dir, "status", "--porcelain").strip())
