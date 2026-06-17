"""Append-only JSONL research log: one entry per iteration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ninexf import LOG_FILENAME


@dataclass
class LogEntry:
    iteration: int
    timestamp: str
    subtask: str
    summary: str
    files_written: list[str] = field(default_factory=list)
    validation_passed: bool | None = None
    validation_detail: str = ""
    errors: list[str] = field(default_factory=list)
    soft_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    commit: str = ""
    event: str = "iteration"  # iteration | startup | shutdown | violation | decompose | verify | finished | revert | explore | restore_best
    mode: str = "build"  # build | fix | review | verify_done
    stuck_detected: bool = False
    stuck_signals: list[str] = field(default_factory=list)  # repeat | oscillation | no_writes | same_error
    reverted_to: str = ""  # commit hash, on revert events
    regression: bool = False
    tests_ran: int = 0
    tool_runs: list[dict] = field(default_factory=list)  # {name, args, result}
    task_id: int = 0  # which TASKS.md task this iteration targeted (0 = none/unknown)
    tasks_done: int = 0
    tasks_total: int = 0
    context_files: list[str] = field(default_factory=list)  # files shown to the executor
    notes_added: list[str] = field(default_factory=list)
    acceptance_passed: bool | None = None  # held-out suite (None = no suite)
    acceptance_ran: int = 0
    critic_verdict: str = ""  # ACCEPT | REVISE | unparsed | "" (critic off/skipped)
    critic_issues: list[str] = field(default_factory=list)
    critic_revised: bool = False
    candidates: list[dict] = field(default_factory=list)  # best-of-N losers + winner meta
    chosen_candidate: int = 0
    explore: dict = field(default_factory=dict)  # {a: {...}, b: {...}, winner} on explore events
    repairs: list[dict] = field(default_factory=list)  # in-iteration repair attempts {attempt, errors_before, passed}
    model_calls: list[dict] = field(default_factory=list)  # per-call purpose, size, latency, errors
    context_overflow: bool = False  # a prompt filled num_ctx (silent top-truncation risk)
    failure_kind: str = ""  # compile | import | entry | slow_entry | tests | timeout | slow_test | frontend_static | tool | parse
    error_signature: str = ""  # normalized first-error signature for stuck/diagnosis
    error_excerpt: str = ""  # capped actionable validation evidence
    diagnosis: str = ""  # optional no-write diagnosis before repeated repairs
    quality_status: str = ""  # READY | NEEDS_MORE_WORK | ""
    quality_score: int = 0  # summed 0-25 score from quality review
    quality_scores: dict[str, int] = field(default_factory=dict)
    quality_issues: list[str] = field(default_factory=list)
    quality_next_focus: str = ""
    quality_summary: str = ""
    product_signature: str = ""
    product_changed: bool = False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# In-process memo of the parsed log, keyed by absolute path -> (size, mtime_ns,
# entries). loop_log.jsonl is append-only within a run, and a single iteration
# calls read_entries() ~20 times (planning, recovery, stuck detection, quality,
# history). Re-reading and JSON-parsing the whole (ever-growing) file each time
# is O(n) per call and O(n²) over a long run — the late hours of an overnight
# run slow to a crawl. This cache makes read_entries O(1) on a hit; append_entry
# keeps it in lockstep so the file is parsed at most once per appended line.
# Correctness rests on (size, mtime_ns) validation: any write the cache didn't
# perform (another process, a resume) shows up as a mismatch and forces a full
# reparse. Callers treat the result as read-only (verified at every call site).
_CACHE: dict[str, tuple[int, int, list[dict]]] = {}


def _parse_log(path: Path) -> list[dict]:
    entries: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"event": "corrupt-line", "raw": line[:200]})
    return entries


def append_entry(project_dir: Path, entry: LogEntry) -> None:
    path = project_dir / LOG_FILENAME
    record = asdict(entry)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    # Keep the parse cache current instead of invalidating it: extend the cached
    # list and re-stamp (size, mtime_ns) from the file we just wrote, so the next
    # read_entries() this iteration is a cache hit rather than a full reparse.
    key = str(path)
    cached = _CACHE.get(key)
    if cached is None:
        return  # cold: let the next read_entries() do the initial parse
    try:
        st = path.stat()
    except OSError:
        _CACHE.pop(key, None)
        return
    entries = cached[2]
    entries.append(record)
    _CACHE[key] = (st.st_size, st.st_mtime_ns, entries)


def read_entries(project_dir: Path) -> list[dict]:
    path = project_dir / LOG_FILENAME
    key = str(path)
    try:
        st = path.stat()
    except OSError:
        _CACHE.pop(key, None)
        return []
    cached = _CACHE.get(key)
    if cached is not None and cached[0] == st.st_size and cached[1] == st.st_mtime_ns:
        return cached[2]
    entries = _parse_log(path)
    _CACHE[key] = (st.st_size, st.st_mtime_ns, entries)
    return entries


def last_iteration_number(project_dir: Path) -> int:
    nums = [e.get("iteration", 0) for e in read_entries(project_dir) if e.get("event") == "iteration"]
    return max(nums, default=0)
