"""Arena mode (v0.5): a successive-halving tournament for one machine.

The failure mode keep_best can't fix is a run whose *plan* was bad from
iteration 1 — it never reaches a good state to checkpoint. The arena answers
"was my first decomposition a dud?" in the first hour instead of at 7am:

  1. K independent seed runs of the same goal (each gets its own decomposition;
     sampling temperature is varied per seed for diversity)
  2. each seed gets a short burst — half the total budget split K ways
  3. seeds are scored with the keep_best fitness tuple; the winner gets the
     entire remaining half of the night

Sequential on purpose: on one machine parallel runs buy nothing (Ollama
serializes inference), so the arena allocates the same total compute as one
long run — diversity early, depth late, zero extra RAM. A seed that FINISHES
during its burst wins immediately.

All seeds share one held-out acceptance suite (generated once, copied), so
their fitness scores are comparable.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ninexf import GOAL_FILENAME
from ninexf.config import load_config, write_config
from ninexf.fitness import best_state, fitness_of
from ninexf.gitops import commit_all, init_repo
from ninexf.looplog import read_entries
from ninexf.registry import register_run

# varied per seed so the decompositions and code actually differ
SEED_TEMPERATURES = (0.4, 0.7, 0.9, 0.55, 0.8, 0.3, 0.65, 1.0)

NO_SCORE = (-1,)  # sorts below every real fitness tuple


def _init_seed(seed_dir: Path, goal: str, model: str | None, preset: str | None,
               temperature: float, overrides: dict | None = None) -> None:
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "src").mkdir(exist_ok=True)
    (seed_dir / "tests").mkdir(exist_ok=True)
    (seed_dir / "tests" / "__init__.py").touch()
    (seed_dir / "tools").mkdir(exist_ok=True)
    (seed_dir / GOAL_FILENAME).write_text(goal.strip() + "\n")
    merged = {"model": model, "temperature": temperature}
    merged.update(overrides or {})
    write_config(seed_dir, merged, preset=preset)
    (seed_dir / ".gitignore").write_text("__pycache__/\n*.pyc\nstate.json\n")
    if not (seed_dir / ".git").exists():
        init_repo(seed_dir)
    commit_all(seed_dir, "9xf arena seed: goal and config", allow_empty=True)
    register_run(seed_dir, goal.strip())


def _share_acceptance(seed_dirs: list[Path], goal: str) -> None:
    """Generate the held-out suite once (in seed 1) and copy it to every seed,
    so the per-seed fitness scores measure the same thing."""
    from ninexf.cli import _generate_acceptance_tests
    first = seed_dirs[0]
    _generate_acceptance_tests(first, goal)
    suite = first / "acceptance" / "test_acceptance.py"
    if not suite.exists():
        return  # generation degraded gracefully; seeds run criteria-only
    for d in seed_dirs:
        if d == first:
            continue
        (d / "acceptance").mkdir(exist_ok=True)
        shutil.copy2(suite, d / "acceptance" / "test_acceptance.py")
    for d in seed_dirs:
        commit_all(d, "9xf arena: shared held-out acceptance suite", allow_empty=True)


def _seed_score(seed_dir: Path) -> tuple:
    best = best_state(read_entries(seed_dir))
    return fitness_of(best) if best else NO_SCORE


def _finished(seed_dir: Path) -> bool:
    return any(e.get("event") == "finished" for e in read_entries(seed_dir))


def _user_aborted(seed_dir: Path) -> bool:
    entries = read_entries(seed_dir)
    shutdowns = [e for e in entries if e.get("event") == "shutdown"]
    return bool(shutdowns) and "Ctrl+C" in shutdowns[-1].get("summary", "")


def _run_phase(seed_dir: Path, hours: float | None, max_iterations: int | None,
               delay: float | None) -> None:
    from ninexf.loop import LoopRunner
    LoopRunner(seed_dir, load_config(seed_dir)).run(
        max_iterations=max_iterations, delay=delay, hours=hours)


def run_arena(base_dir: Path, goal: str, *, model: str | None = None,
              seeds: int = 3, hours: float = 8.0, preset: str | None = "overnight",
              burst_iterations: int | None = None,
              final_iterations: int | None = None,
              delay: float | None = None,
              config_overrides: dict | None = None) -> Path:
    """Run the tournament. Returns the winning seed's directory.
    hours <= 0 disables wall-clock budgets (then burst/final_iterations bound
    the phases — primarily for the harness's own tests)."""
    seeds = max(2, seeds)
    base_dir.mkdir(parents=True, exist_ok=True)
    burst_h = (hours * 0.5 / seeds) if hours and hours > 0 else None
    final_h = (hours * 0.5) if hours and hours > 0 else None

    print(f"[9xf] arena: {seeds} seeds, "
          + (f"{burst_h:.2f}h burst each, {final_h:.1f}h for the winner"
             if burst_h else "iteration-bounded phases"))
    seed_dirs = [base_dir / f"seed-{i}" for i in range(1, seeds + 1)]
    # overrides apply to every seed; acceptance generation happens once below,
    # so the per-seed init never generates its own
    overrides = dict(config_overrides or {})
    want_acceptance = overrides.pop("acceptance_tests", None)
    for i, d in enumerate(seed_dirs):
        _init_seed(d, goal, model, preset,
                   SEED_TEMPERATURES[i % len(SEED_TEMPERATURES)],
                   {**overrides, "acceptance_tests": False})
    cfg0 = load_config(seed_dirs[0])
    if want_acceptance or (want_acceptance is None and (preset == "overnight"
                                                        or cfg0.acceptance_tests)):
        _share_acceptance(seed_dirs, goal)

    # phase 1: burst every seed
    winner: Path | None = None
    for i, d in enumerate(seed_dirs, start=1):
        print(f"\n[9xf] arena burst {i}/{seeds}: {d.name} "
              f"(temperature {load_config(d).temperature})")
        _run_phase(d, burst_h, burst_iterations, delay)
        if _user_aborted(d):
            print("[9xf] arena aborted by Ctrl+C during burst — scoring what ran")
            break
        if _finished(d):
            print(f"[9xf] arena: {d.name} FINISHED during its burst — instant winner")
            winner = d
            break

    scores = {d.name: _seed_score(d) for d in seed_dirs}
    if winner is None:
        winner = max(seed_dirs, key=lambda d: (scores[d.name], -seed_dirs.index(d)))
    print("\n[9xf] arena scores (acceptance, validation, tasks, tests, -errors):")
    for d in seed_dirs:
        mark = "←  WINNER" if d == winner else ""
        print(f"  {d.name}: {scores[d.name]} {mark}")

    # phase 2: the winner gets the rest of the night
    aborted = any(_user_aborted(d) for d in seed_dirs)
    if not _finished(winner) and not aborted:
        print(f"\n[9xf] arena final: {winner.name} continues with the remaining budget")
        _run_phase(winner, final_h, final_iterations, delay)

    _write_arena_report(base_dir, goal, seed_dirs, winner, scores)
    print(f"\n[9xf] arena complete — winner: {winner}")
    print(f"[9xf] summary written to {base_dir / 'ARENA.md'}")
    return winner


def _write_arena_report(base_dir: Path, goal: str, seed_dirs: list[Path],
                        winner: Path, burst_scores: dict[str, tuple]) -> None:
    lines = [
        "# 9xf arena summary",
        "",
        f"**Goal:** {goal}",
        f"**Seeds:** {len(seed_dirs)}  |  **Winner:** `{winner.name}`",
        "",
        "| seed | temperature | burst score | final score | iterations | finished |",
        "|---|---|---|---|---|---|",
    ]
    for d in seed_dirs:
        entries = read_entries(d)
        iters = sum(1 for e in entries if e.get("event") == "iteration")
        cfg = load_config(d)
        mark = " **(winner)**" if d == winner else ""
        lines.append(
            f"| `{d.name}`{mark} | {cfg.temperature} | {burst_scores.get(d.name)} "
            f"| {_seed_score(d)} | {iters} | "
            f"{'YES' if _finished(d) else 'no'} |")
    lines += [
        "",
        f"Winning run: `{winner}` — inspect with `9xf status --dir {winner}` "
        f"and `9xf report --dir {winner}`.",
    ]
    (base_dir / "ARENA.md").write_text("\n".join(lines) + "\n")
