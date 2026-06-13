"""Bench data model: tasks, experiment cells, and per-cell results.

A task lives on disk under ninexf/bench/tasks/<name>/ as:
  goal.txt              the natural-language contract fed to the loop
  meta.json             {tier, category, max_iterations, hours, allow_network}
  oracle/test_*.py      the fixed, human-authored ground-truth suite

An experiment is JSON under ninexf/bench/experiments/<name>.json describing a
grid of cells (model x preset x overrides) crossed with tasks x seeds.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parent / "tasks"
EXPERIMENTS_DIR = Path(__file__).resolve().parent / "experiments"


@dataclass
class TaskSpec:
    name: str
    dir: Path
    goal: str
    tier: str = "easy"            # easy | medium | hard
    category: str = ""
    max_iterations: int = 25
    hours: float = 0.0            # 0 = no wall-clock cap (use iteration cap)
    allow_network: bool = False

    @property
    def oracle_dir(self) -> Path:
        return self.dir / "oracle"


def load_task(name: str) -> TaskSpec:
    d = TASKS_DIR / name
    if not d.is_dir():
        raise FileNotFoundError(f"no bench task {name!r} under {TASKS_DIR}")
    goal_path = d / "goal.txt"
    if not goal_path.exists():
        raise FileNotFoundError(f"task {name!r} is missing goal.txt")
    if not list((d / "oracle").glob("test_*.py")):
        raise FileNotFoundError(f"task {name!r} has no oracle/test_*.py suite")
    meta = {}
    meta_path = d / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    return TaskSpec(
        name=name,
        dir=d,
        goal=goal_path.read_text().strip(),
        tier=meta.get("tier", "easy"),
        category=meta.get("category", ""),
        max_iterations=int(meta.get("max_iterations", 25)),
        hours=float(meta.get("hours", 0.0)),
        allow_network=bool(meta.get("allow_network", False)),
    )


def all_task_names() -> list[str]:
    return sorted(p.name for p in TASKS_DIR.iterdir()
                  if p.is_dir() and (p / "goal.txt").exists())


@dataclass
class Cell:
    """One experimental condition: a model + preset + config overrides."""
    label: str
    model: str
    preset: str | None = None
    overrides: dict = field(default_factory=dict)


@dataclass
class ExperimentSpec:
    name: str
    description: str
    cells: list[Cell]
    tasks: list[str]
    seeds: int = 1
    reference_cell: str = ""  # label compared against in the pairwise section

    @classmethod
    def load(cls, name: str) -> "ExperimentSpec":
        path = EXPERIMENTS_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"no experiment {name!r} under {EXPERIMENTS_DIR} "
                f"(available: {', '.join(available_experiments()) or 'none'})")
        raw = json.loads(path.read_text())
        cells = [Cell(label=c["label"], model=c["model"],
                      preset=c.get("preset"), overrides=c.get("overrides", {}))
                 for c in raw["cells"]]
        tasks = raw.get("tasks") or ["*"]
        if tasks == ["*"] or tasks == "*":
            tasks = all_task_names()
        return cls(
            name=raw.get("name", name),
            description=raw.get("description", ""),
            cells=cells,
            tasks=tasks,
            seeds=int(raw.get("seeds", 1)),
            reference_cell=raw.get("reference_cell", ""),
        )


def available_experiments() -> list[str]:
    if not EXPERIMENTS_DIR.is_dir():
        return []
    return sorted(p.stem for p in EXPERIMENTS_DIR.glob("*.json"))


@dataclass
class CellResult:
    """One scored run: a (cell, task, seed) triple graded by the oracle."""
    experiment: str
    cell: str
    model: str
    preset: str | None
    task: str
    tier: str
    seed: int
    oracle_passed: bool
    oracle_tests_ran: int
    oracle_detail: str
    finished: bool                  # loop's own verify_done declared complete
    iterations: int
    first_green_iteration: int | None
    wall_clock_s: float
    model_calls: int
    prompt_chars: int
    response_chars: int
    model_latency_s: float
    error: str = ""                 # runner-level failure (run crashed, etc.)

    def to_dict(self) -> dict:
        return asdict(self)
