"""Run benchmark experiments: drive a loop per cell, then grade it blind.

The discipline that makes results falsifiable:
  - The solver never sees and never authors the oracle (acceptance_tests is
    forced OFF; the oracle is copied in only AFTER the run, in a separate
    sandboxed process).
  - The oracle is identical across every model and config, so a pass means the
    code actually meets the contract — not that the model graded itself kindly.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from pathlib import Path

from ninexf.bench import BENCH_RESULTS_FILENAME, ORACLE_SUITE_DIRNAME
from ninexf.bench.spec import Cell, CellResult, ExperimentSpec, TaskSpec, load_task
from ninexf.config import load_config, write_config
from ninexf.looplog import read_entries
from ninexf.validate import run_sandboxed

ORACLE_TIMEOUT = 30  # seconds for the held-out oracle suite


def _init_cell_project(project: Path, task: TaskSpec, cell: Cell) -> None:
    """Create a fresh run folder for one cell, with the oracle held out.

    We init with base defaults (so init never triggers model-authored
    acceptance tests), then rewrite the config deterministically with the
    cell's preset + overrides and acceptance_tests forced OFF.
    """
    from ninexf.cli import init_project  # late import: keeps `bench report` fast

    if project.exists():
        shutil.rmtree(project)
    init_project(project, task.goal, acceptance_tests=False,
                 allow_network=task.allow_network, force=True)
    overrides = dict(cell.overrides)
    overrides["model"] = cell.model
    overrides["acceptance_tests"] = False  # external oracle is the only judge
    if task.allow_network:
        overrides["allow_network"] = True
    write_config(project, overrides=overrides, preset=cell.preset)


def score_oracle(project: Path, task: TaskSpec) -> tuple[bool, int, str]:
    """Run the task's fixed oracle suite against the finished project, blind.

    Returns (passed, tests_ran, detail). Reuses validate.run_sandboxed so the
    oracle inherits the same stripped-env / deny-network sandbox as validation.
    """
    suite = project / ORACLE_SUITE_DIRNAME
    if suite.exists():
        shutil.rmtree(suite)
    suite.mkdir()
    (suite / "__init__.py").touch()
    for f in task.oracle_dir.glob("test_*.py"):
        shutil.copy(f, suite / f.name)
    rc, out = run_sandboxed(
        project,
        [sys.executable, "-m", "unittest", "discover", "-s", ORACLE_SUITE_DIRNAME, "-t", "."],
        ORACLE_TIMEOUT, task.allow_network,
    )
    shutil.rmtree(suite, ignore_errors=True)  # keep the run dir = solver output only
    import re
    m = re.search(r"Ran (\d+) tests?", out)
    ran = int(m.group(1)) if m else 0
    passed = rc == 0 and ran > 0
    return passed, ran, out.strip()[-1200:]


def _run_metrics(project: Path) -> dict:
    """Aggregate loop_log.jsonl into the run-level metrics bench reports on."""
    entries = read_entries(project)
    iters = [e for e in entries if e.get("event") == "iteration"]
    greens = [e["iteration"] for e in iters if e.get("validation_passed")]
    calls = [c for e in entries for c in e.get("model_calls", [])]
    return {
        "iterations": len(iters),
        "finished": any(e.get("event") == "finished" for e in entries),
        "first_green_iteration": min(greens) if greens else None,
        "model_calls": len(calls),
        "prompt_chars": sum(int(c.get("prompt_chars", 0)) for c in calls),
        "response_chars": sum(int(c.get("response_chars", 0)) for c in calls),
        "model_latency_s": round(sum(float(c.get("latency_s", 0.0)) for c in calls), 3),
    }


def run_cell(experiment: str, task: TaskSpec, cell: Cell, seed: int,
             workspace: Path) -> CellResult:
    """Init, run, and grade a single (cell, task, seed) triple."""
    project = workspace / f"{cell.label}__{task.name}__s{seed}"
    base = dict(
        experiment=experiment, cell=cell.label, model=cell.model, preset=cell.preset,
        task=task.name, tier=task.tier, seed=seed,
    )
    try:
        _init_cell_project(project, task, cell)
        config = load_config(project)
        # Resolve the run budget: a cell may stretch it (overnight), else the task caps it.
        max_iterations = int(cell.overrides.get("max_iterations", task.max_iterations))
        hours = float(cell.overrides.get("max_hours", task.hours)) or None
        delay = float(cell.overrides.get("delay_seconds", 0))

        from ninexf.loop import LoopRunner  # late import keeps report path light
        started = time.perf_counter()
        LoopRunner(project, config).run(max_iterations=max_iterations, delay=delay, hours=hours)
        wall = round(time.perf_counter() - started, 2)

        passed, ran, detail = score_oracle(project, task)
        metrics = _run_metrics(project)
        return CellResult(
            **base, oracle_passed=passed, oracle_tests_ran=ran, oracle_detail=detail,
            wall_clock_s=wall, **metrics,
        )
    except Exception as e:  # noqa: BLE001 - a crashed run is a recorded failure, not a stop
        return CellResult(
            **base, oracle_passed=False, oracle_tests_ran=0,
            oracle_detail=f"{e}\n{traceback.format_exc()[-800:]}",
            finished=False, iterations=0, first_green_iteration=None,
            wall_clock_s=0.0, model_calls=0, prompt_chars=0, response_chars=0,
            model_latency_s=0.0, error=str(e)[:300],
        )


def run_experiment(exp: ExperimentSpec, out_dir: Path,
                   progress=print) -> list[CellResult]:
    """Run every (cell, task, seed) triple and persist bench_results.json."""
    workspace = out_dir / "runs" / exp.name
    workspace.mkdir(parents=True, exist_ok=True)
    tasks = [load_task(name) for name in exp.tasks]
    total = len(exp.cells) * len(tasks) * exp.seeds
    results: list[CellResult] = []
    n = 0
    for cell in exp.cells:
        for task in tasks:
            for seed in range(exp.seeds):
                n += 1
                progress(f"[bench] ({n}/{total}) {cell.label} · {task.name} · seed {seed}")
                r = run_cell(exp.name, task, cell, seed, workspace)
                mark = "PASS" if r.oracle_passed else ("ERR " if r.error else "FAIL")
                progress(f"        -> {mark} ({r.oracle_tests_ran} oracle tests, "
                         f"{r.iterations} iters, {r.wall_clock_s}s)")
                results.append(r)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": exp.name,
        "description": exp.description,
        "seeds": exp.seeds,
        "reference_cell": exp.reference_cell,
        "results": [r.to_dict() for r in results],
    }
    (out_dir / BENCH_RESULTS_FILENAME).write_text(json.dumps(payload, indent=2) + "\n")
    progress(f"[bench] wrote {out_dir / BENCH_RESULTS_FILENAME}")
    return results
