"""Task list and acceptance criteria: TASKS.md + ACCEPTANCE.md.

Both files are harness-managed (the agent reads them in its prompts but cannot
write them — root-level files are outside the sandbox's writable dirs). They
are committed, so task-state changes are part of the research artifact.

TASKS.md format (line-oriented so a 7B model reads it fluently):

    [ ] T1: todo
    [~] T2: in progress
    [x] T3: done
    [!] T4: deferred (failed too many times)

ACCEPTANCE.md format:

    C1: one observable, checkable statement

Unparseable lines are kept verbatim (never destroyed) and reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TASKS_FILENAME = "TASKS.md"
ACCEPTANCE_FILENAME = "ACCEPTANCE.md"

TASKS_HEADER = "# 9xf tasks — managed by the harness, do not edit"
ACCEPTANCE_HEADER = "# Acceptance criteria — managed by the harness"

TASK_LINE_RE = re.compile(r"^\[(?P<status>.)\]\s*T(?P<num>\d+):\s*(?P<text>.+?)\s*$")
CRITERION_LINE_RE = re.compile(r"^C(?P<num>\d+):\s*(?P<text>.+?)\s*$")

# Decompose-output parsing: tolerate "- TASK:", "1. TASK:", "TASK 3:", etc.
DECOMPOSE_TASK_RE = re.compile(r"^[\s\-*]*(?:\d+[.)]\s*)?TASK(?:\s*\d*)?:\s*(?P<text>.+?)\s*$")
DECOMPOSE_CRITERION_RE = re.compile(
    r"^[\s\-*]*(?:\d+[.)]\s*)?CRITERION(?:\s*\d*)?:\s*(?P<text>.+?)\s*$"
)

STATUS_TODO = " "
STATUS_IN_PROGRESS = "~"
STATUS_DONE = "x"
STATUS_DEFERRED = "!"

BAD_DECOMPOSITION_PATTERNS = (
    "venv",
    "virtual environment",
    "activate",
    ".gitignore",
    "pip install",
    "npm install",
    "package install",
    "install dependencies",
    "flake8",
    "pytest",
)

BAD_CRITERION_PATTERNS = (
    "created and empty",
    "exists and is empty",
    "file is empty",
)

ROOT_WRITE_PATTERNS = (
    "root",
    "project root",
    "repo root",
)

ALLOWED_GENERATED_DIRS = {"src", "tests", "tools"}


@dataclass
class Task:
    num: int
    text: str
    status: str = STATUS_TODO  # " " | "~" | "x" | "!"

    @property
    def open(self) -> bool:
        return self.status in (STATUS_TODO, STATUS_IN_PROGRESS)


@dataclass
class TaskList:
    tasks: list[Task] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)  # kept verbatim, reported

    def get(self, num: int) -> Task | None:
        for t in self.tasks:
            if t.num == num:
                return t
        return None

    def open_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.open]

    def eligible_task(self) -> Task | None:
        """The next task the planner may execute.

        TASKS.md is ordered work. Allowing arbitrary open tasks lets small
        models jump ahead to tests or polish before the core API exists, which
        was a major Run4 failure mode.
        """
        return next((t for t in sorted(self.tasks, key=lambda t: t.num) if t.open), None)

    def all_resolved(self) -> bool:
        return bool(self.tasks) and not self.open_tasks()

    def counts(self) -> tuple[int, int]:
        """(done, total) — deferred tasks count as resolved but not done."""
        done = sum(1 for t in self.tasks if t.status == STATUS_DONE)
        return done, len(self.tasks)

    def next_num(self) -> int:
        return max((t.num for t in self.tasks), default=0) + 1


def tasks_path(project_dir: Path) -> Path:
    return project_dir / TASKS_FILENAME


def acceptance_path(project_dir: Path) -> Path:
    return project_dir / ACCEPTANCE_FILENAME


def load_tasks(project_dir: Path) -> TaskList:
    path = tasks_path(project_dir)
    tl = TaskList()
    if not path.exists():
        return tl
    for line in path.read_text().splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = TASK_LINE_RE.match(line)
        if m:
            tl.tasks.append(Task(
                num=int(m.group("num")),
                text=m.group("text"),
                status=m.group("status"),
            ))
        else:
            tl.unparsed.append(line)
    return tl


def save_tasks(project_dir: Path, tl: TaskList) -> None:
    lines = [TASKS_HEADER]
    for t in sorted(tl.tasks, key=lambda t: t.num):
        lines.append(f"[{t.status}] T{t.num}: {t.text}")
    lines += tl.unparsed  # never destroy lines we couldn't parse
    tasks_path(project_dir).write_text("\n".join(lines) + "\n")


def load_criteria(project_dir: Path) -> list[tuple[int, str]]:
    path = acceptance_path(project_dir)
    if not path.exists():
        return []
    criteria = []
    for line in path.read_text().splitlines():
        m = CRITERION_LINE_RE.match(line.rstrip())
        if m:
            criteria.append((int(m.group("num")), m.group("text")))
    return criteria


def save_criteria(project_dir: Path, criteria: list[str]) -> None:
    lines = [ACCEPTANCE_HEADER]
    lines += [f"C{i}: {text}" for i, text in enumerate(criteria, start=1)]
    acceptance_path(project_dir).write_text("\n".join(lines) + "\n")


def parse_decomposition(text: str) -> tuple[list[str], list[str]]:
    """Extract TASK:/CRITERION: lines from a decompose-mode model reply."""
    tasks, criteria = [], []
    for line in text.splitlines():
        m = DECOMPOSE_TASK_RE.match(line)
        if m:
            tasks.append(m.group("text"))
            continue
        m = DECOMPOSE_CRITERION_RE.match(line)
        if m:
            criteria.append(m.group("text"))
    return tasks, criteria


def _mentions_forbidden_path(text: str) -> bool:
    """True when a generated task points at an obvious non-writable file/path."""
    lowered = text.lower()
    if any(p in lowered for p in ROOT_WRITE_PATTERNS):
        return True
    paths = re.findall(r"`([^`]+)`|(?:^|\s)([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)", text)
    for quoted, bare in paths:
        candidate = (quoted or bare).strip()
        if not candidate or "/" not in candidate:
            continue
        tokens = [candidate] if bare else candidate.split()
        path_tokens = [
            token.strip(".,;:()[]{}\"'")
            for token in tokens
            if "/" in token
        ]
        for token in path_tokens:
            first = token.split("/", 1)[0]
            if first not in ALLOWED_GENERATED_DIRS:
                return True
        if not path_tokens:
            return True
    return False


def sanitize_decomposition(
    goal: str,
    tasks: list[str],
    criteria: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Drop generated work items that violate harness constraints.

    The goal is allowed to explicitly request unusual setup. Otherwise,
    decomposition must stay inside the write sandbox and stdlib test harness.
    Returns (tasks, criteria, rejection reasons).
    """
    goal_l = goal.lower()
    rejections: list[str] = []

    def keep(kind: str, text: str) -> bool:
        lowered = text.lower()
        hits = [p for p in BAD_DECOMPOSITION_PATTERNS
                if p in lowered and p not in goal_l]
        if kind == "CRITERION":
            hits.extend(p for p in BAD_CRITERION_PATTERNS
                        if p in lowered and p not in goal_l)
        if hits or (_mentions_forbidden_path(text) and "root" not in goal_l):
            reason = ", ".join(hits) if hits else "non-writable/root path"
            rejections.append(f"{kind}: {text} ({reason})")
            return False
        return True

    clean_tasks = [t for t in tasks if keep("TASK", t)]
    clean_criteria = [c for c in criteria if keep("CRITERION", c)]
    return clean_tasks, clean_criteria, rejections


def mark_status(project_dir: Path, num: int, status: str) -> None:
    tl = load_tasks(project_dir)
    task = tl.get(num)
    if task is None:
        return
    task.status = status
    save_tasks(project_dir, tl)


def append_tasks(project_dir: Path, texts: list[str]) -> list[int]:
    """Add new tasks (e.g. corrective tasks from a verify-done FAIL)."""
    tl = load_tasks(project_dir)
    nums = []
    for text in texts:
        num = tl.next_num()
        tl.tasks.append(Task(num=num, text=text))
        nums.append(num)
    save_tasks(project_dir, tl)
    return nums


def tasks_for_prompt(project_dir: Path) -> str:
    """The task-list section shown to the planner."""
    tl = load_tasks(project_dir)
    if not tl.tasks:
        return ""
    eligible = tl.eligible_task()
    lines = ["Eligible next task:"]
    if eligible:
        status = "in progress" if eligible.status == STATUS_IN_PROGRESS else "open"
        lines.append(f"  T{eligible.num} ({status}): {eligible.text}")
    else:
        lines.append("  (none)")
    queued_lines = []
    deferred_lines = []
    for t in sorted(tl.tasks, key=lambda t: t.num):
        label = {STATUS_TODO: "open", STATUS_IN_PROGRESS: "in progress",
                 STATUS_DONE: "DONE", STATUS_DEFERRED: "deferred"}.get(t.status, "open")
        line = f"  T{t.num} ({label}): {t.text}"
        if t.status == STATUS_DEFERRED:
            deferred_lines.append(f"  T{t.num} (deferred, not eligible): {t.text}")
        elif eligible and t.num == eligible.num:
            continue
        elif t.open:
            queued_lines.append(f"  T{t.num} (queued, not eligible yet): {t.text}")
        else:
            queued_lines.append(line)
    if queued_lines:
        lines.append("Queued/resolved tasks:")
        lines.extend(queued_lines)
    if deferred_lines:
        lines.append("Deferred tasks (not eligible unless verify-done creates a new corrective task):")
        lines.extend(deferred_lines)
    return "\n".join(lines)


def criteria_for_prompt(project_dir: Path) -> str:
    criteria = load_criteria(project_dir)
    return "\n".join(f"  C{n}: {text}" for n, text in criteria)


def parse_task_ref(subtask: str, tl: TaskList) -> int:
    """Pull a leading 'TASK Tn:' reference out of a planner reply.
    Returns the task number only when it is the current eligible task;
    otherwise 0."""
    m = re.match(r"\s*TASK\s+T?(\d+)\s*:?", subtask, re.IGNORECASE)
    if not m:
        return 0
    num = int(m.group(1))
    eligible = tl.eligible_task()
    return num if eligible and eligible.num == num else 0


def parse_task_ref_num(subtask: str) -> int:
    """Return the mentioned task number even if unknown/deferred."""
    m = re.match(r"\s*TASK\s+T?(\d+)\s*:?", subtask, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def strip_task_ref(subtask: str) -> str:
    """Remove the 'TASK Tn:' prefix so the executor sees a clean instruction."""
    return re.sub(r"^\s*TASK\s+T?\d+\s*:?\s*", "", subtask, flags=re.IGNORECASE).strip() or subtask


VERDICT_PASS_RE = re.compile(r"^[\s\-*]*PASS:?\s*C?(?P<num>\d+)", re.IGNORECASE)
VERDICT_FAIL_RE = re.compile(
    r"^[\s\-*]*FAIL:?\s*C?(?P<num>\d+)\s*(?:[—\-:]\s*(?P<reason>.+))?", re.IGNORECASE
)


def parse_verify_output(text: str) -> tuple[set[int], dict[int, str]]:
    """Parse PASS: Cn / FAIL: Cn — reason lines from a verify-done reply.
    Returns (passed_nums, {failed_num: reason})."""
    passed: set[int] = set()
    failed: dict[int, str] = {}
    for line in text.splitlines():
        m = VERDICT_FAIL_RE.match(line)
        if m:
            failed[int(m.group("num"))] = (m.group("reason") or "").strip()
            continue
        m = VERDICT_PASS_RE.match(line)
        if m:
            passed.add(int(m.group("num")))
    return passed, failed
