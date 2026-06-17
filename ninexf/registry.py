"""Global registry of run folders (~/.9xf/registry.json) plus per-run
state.json heartbeats — what `9xf watch` reads to show every loop at once.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ninexf import GOAL_FILENAME

REGISTRY_DIR = Path.home() / ".9xf"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"
STATE_FILENAME = "state.json"
MAX_ACTIVITY = 80


def _registry_dir() -> Path:
    return Path(os.environ.get("NINEXF_REGISTRY_DIR", str(REGISTRY_DIR))).expanduser()


def _registry_file() -> Path:
    return _registry_dir() / "registry.json"


def _load() -> list[dict]:
    path = _registry_file()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def register_run(project_dir: Path, goal: str, started: str | None = None) -> None:
    _registry_dir().mkdir(parents=True, exist_ok=True)
    entries = [e for e in _load() if e.get("dir") != str(project_dir)]
    entries.append({"dir": str(project_dir), "goal": goal, "last_started": started})
    _registry_file().write_text(json.dumps(entries, indent=2))


def registered_runs() -> list[Path]:
    """Registered run dirs that still exist (stale entries pruned)."""
    live, entries = [], _load()
    kept = []
    for e in entries:
        p = Path(e.get("dir", ""))
        if p.is_dir() and (p / GOAL_FILENAME).exists():
            live.append(p)
            kept.append(e)
    path = _registry_file()
    if len(kept) != len(entries) and path.exists():
        path.write_text(json.dumps(kept, indent=2))
    return live


def write_state(project_dir: Path, **fields) -> None:
    prev = read_state(project_dir)
    state = {"pid": os.getpid(), **fields}
    if "activity" not in fields and prev.get("activity"):
        state["activity"] = prev["activity"][-MAX_ACTIVITY:]
    (project_dir / STATE_FILENAME).write_text(json.dumps(state, indent=2))


def append_activity(
    project_dir: Path,
    message: str,
    *,
    iteration: int | None = None,
    kind: str = "activity",
) -> None:
    """Append a lightweight live status line to state.json for the app."""
    state = read_state(project_dir)
    activity = list(state.get("activity") or [])
    activity.append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "iteration": iteration if iteration is not None else state.get("iteration", 0),
        "kind": kind,
        "message": message[:500],
    })
    state["activity"] = activity[-MAX_ACTIVITY:]
    state.setdefault("running", True)
    state.setdefault("pid", os.getpid())
    (project_dir / STATE_FILENAME).write_text(json.dumps(state, indent=2))


def read_state(project_dir: Path) -> dict:
    p = project_dir / STATE_FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def _pid_alive(pid: object) -> bool:
    try:
        n = int(pid)
    except (TypeError, ValueError):
        return False
    if n <= 0:
        return False
    try:
        os.kill(n, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return False
    return True


def other_active_runs(except_dir: Path) -> list[Path]:
    """Registered runs (other than except_dir) whose state.json says running and
    whose pid is still alive. Local model runs all share one Ollama server, which
    serializes inference and reloads VRAM whenever consecutive runs use different
    models — so a stack of concurrent runs makes each one crawl. The loop warns
    about this at startup instead of silently grinding."""
    try:
        except_resolved = except_dir.resolve()
    except OSError:
        except_resolved = except_dir
    active: list[Path] = []
    for other in registered_runs():
        try:
            other_resolved = other.resolve()
        except OSError:
            other_resolved = other
        if other_resolved == except_resolved:
            continue
        st = read_state(other)
        if st.get("running") and _pid_alive(st.get("pid")):
            active.append(other)
    return active
