"""Shallow validation: does the code parse, and does the entry point run.

Per the PRD this is intentionally not semantic. Runs happen in a subprocess
with a stripped environment and a timeout. On macOS, when allow_network is
false, the run is wrapped in sandbox-exec with a deny-network profile
(best-effort: falls back to an unwrapped run if sandbox-exec is unavailable).
"""

from __future__ import annotations

import py_compile
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DENY_NETWORK_PROFILE = '(version 1)(allow default)(deny network*)'


@dataclass
class ValidationResult:
    passed: bool
    detail: str = ""
    errors: list[str] = field(default_factory=list)


def _compile_check(paths: list[Path]) -> list[str]:
    errors = []
    for p in paths:
        if p.suffix != ".py":
            continue
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"{p.name}: {e.msg.strip().splitlines()[-1] if e.msg else 'syntax error'}")
        except Exception as e:  # unreadable file etc.
            errors.append(f"{p.name}: {e}")
    return errors


def _entry_point(project_dir: Path) -> Path | None:
    for candidate in ("src/main.py", "src/app.py", "src/cli.py"):
        p = project_dir / candidate
        if p.exists():
            return p
    return None


def _run_command(project_dir: Path, script: Path, timeout: float, allow_network: bool) -> list[str]:
    cmd = [sys.executable, str(script.relative_to(project_dir))]
    if not allow_network and sys.platform == "darwin":
        sandboxed = ["sandbox-exec", "-p", DENY_NETWORK_PROFILE, *cmd]
        probe = subprocess.run(
            ["sandbox-exec", "-p", DENY_NETWORK_PROFILE, "true"],
            capture_output=True, cwd=project_dir,
        )
        if probe.returncode == 0:
            cmd = sandboxed
    env = {"PATH": "/usr/bin:/bin", "HOME": str(project_dir)}
    try:
        result = subprocess.run(
            cmd, cwd=project_dir, env=env,
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return [f"{script.name}: timed out after {timeout}s"]
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-5:]
        return [f"{script.name}: exit {result.returncode}: " + " | ".join(tail)]
    return []


def validate(
    project_dir: Path,
    written_files: list[Path],
    timeout: float,
    allow_network: bool,
) -> ValidationResult:
    errors = _compile_check(written_files)
    ran = "compile-check only"
    if not errors:
        entry = _entry_point(project_dir)
        if entry is not None:
            errors = _run_command(project_dir, entry, timeout, allow_network)
            ran = f"compiled + ran {entry.relative_to(project_dir)}"
    return ValidationResult(passed=not errors, detail=ran, errors=errors)
