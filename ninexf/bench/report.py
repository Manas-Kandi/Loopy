"""Aggregate bench_results.json into BENCH.md — the curve that answers the thesis.

Per cell: pass-rate with a 95% Wilson interval (stable for the small n a local
benchmark produces), pass@k across seeds, and resource cost. Plus a pairwise
section comparing each cell to a reference (e.g. overnight vs baseline) with the
pass-rate delta and Cohen's h effect size, and a per-task pass matrix.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from ninexf.bench import BENCH_REPORT_FILENAME, BENCH_RESULTS_FILENAME


def load_results(out_dir: Path) -> dict:
    path = out_dir / BENCH_RESULTS_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"no {BENCH_RESULTS_FILENAME} in {out_dir} — run `9xf bench run` first")
    return json.loads(path.read_text())


def wilson_interval(passes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = passes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def cohens_h(p1: float, p2: float) -> float:
    """Effect size for the difference between two proportions."""
    phi = lambda p: 2 * math.asin(math.sqrt(min(1.0, max(0.0, p))))
    return phi(p1) - phi(p2)


def _h_label(h: float) -> str:
    a = abs(h)
    if a < 0.2:
        return "negligible"
    if a < 0.5:
        return "small"
    if a < 0.8:
        return "medium"
    return "large"


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def summarize(payload: dict) -> dict:
    """Compute per-cell aggregates and pairwise comparisons."""
    results = payload.get("results", [])
    seeds = int(payload.get("seeds", 1))
    by_cell: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_cell[r["cell"]].append(r)

    cells = {}
    for label, rows in by_cell.items():
        n = len(rows)
        passes = sum(1 for r in rows if r["oracle_passed"])
        errors = sum(1 for r in rows if r.get("error"))
        lo, hi = wilson_interval(passes, n)
        # pass@k across seeds: fraction of tasks solved at least once.
        by_task: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_task[r["task"]].append(r)
        pass_at_k = _mean([1.0 if any(t["oracle_passed"] for t in ts) else 0.0
                           for ts in by_task.values()])
        passing = [r for r in rows if r["oracle_passed"]]
        cells[label] = {
            "model": rows[0]["model"],
            "preset": rows[0]["preset"],
            "n": n,
            "passes": passes,
            "errors": errors,
            "pass_rate": passes / n if n else 0.0,
            "ci": (lo, hi),
            "pass_at_1": passes / n if n else 0.0,
            "pass_at_k": pass_at_k,
            "mean_iters": _mean([r["iterations"] for r in rows]),
            "mean_wall": _mean([r["wall_clock_s"] for r in rows]),
            "mean_calls": _mean([float(r["model_calls"]) for r in rows]),
            "mean_chars": _mean([float(r["prompt_chars"] + r["response_chars"]) for r in rows]),
            "wall_to_pass": _mean([r["wall_clock_s"] for r in passing]),
            "green_to_pass": _mean([r["first_green_iteration"] for r in passing
                                    if r["first_green_iteration"] is not None]),
        }

    ref = payload.get("reference_cell") or ""
    pairwise = []
    if ref and ref in cells:
        for label, c in cells.items():
            if label == ref:
                continue
            p1, p2 = c["pass_rate"], cells[ref]["pass_rate"]
            h = cohens_h(p1, p2)
            pairwise.append({
                "cell": label, "ref": ref,
                "delta": p1 - p2, "h": h, "h_label": _h_label(h),
            })

    # per-task matrix: passes/seeds per (task, cell)
    tasks = sorted({r["task"] for r in results})
    tiers = {r["task"]: r["tier"] for r in results}
    matrix = {}
    for task in tasks:
        matrix[task] = {}
        for label, rows in by_cell.items():
            ts = [r for r in rows if r["task"] == task]
            matrix[task][label] = (sum(1 for r in ts if r["oracle_passed"]), len(ts))
    return {
        "cells": cells, "pairwise": pairwise, "matrix": matrix,
        "tiers": tiers, "seeds": seeds, "reference_cell": ref,
    }


def render_markdown(payload: dict, summary: dict) -> str:
    cells = summary["cells"]
    order = list(cells)
    lines: list[str] = []
    lines.append(f"# Benchmark: {payload.get('experiment', '?')}")
    lines.append("")
    if payload.get("description"):
        lines.append(f"_{payload['description']}_")
        lines.append("")
    lines.append(f"Seeds per (cell, task): **{summary['seeds']}**. "
                 "Pass = the fixed external oracle suite passed; the solver never "
                 "saw or wrote the oracle.")
    lines.append("")

    # Summary table
    lines.append("## Pass rates")
    lines.append("")
    lines.append("| Cell | Model | Preset | n | Pass | Pass-rate | 95% CI | pass@k | "
                 "Mean iters | Mean wall (s) | Mean calls |")
    lines.append("|---|---|---|--:|--:|--:|:--:|--:|--:|--:|--:|")
    for label in order:
        c = cells[label]
        lo, hi = c["ci"]
        lines.append(
            f"| {label} | `{c['model']}` | {c['preset'] or '—'} | {c['n']} | "
            f"{c['passes']} | {c['pass_rate']:.0%} | "
            f"{lo:.0%}–{hi:.0%} | {c['pass_at_k']:.0%} | "
            f"{c['mean_iters']:.1f} | {c['mean_wall']:.1f} | {c['mean_calls']:.1f} |")
    lines.append("")

    # Pairwise
    if summary["pairwise"]:
        ref = summary["reference_cell"]
        lines.append(f"## Effect vs reference (`{ref}`)")
        lines.append("")
        lines.append("| Cell | Δ pass-rate | Cohen's h | Effect |")
        lines.append("|---|--:|--:|:--:|")
        for p in summary["pairwise"]:
            sign = "+" if p["delta"] >= 0 else ""
            lines.append(f"| {p['cell']} | {sign}{p['delta']:.0%} | "
                         f"{p['h']:+.2f} | {p['h_label']} |")
        lines.append("")

    # Per-task matrix
    lines.append("## Per-task results (passes / seeds)")
    lines.append("")
    header = "| Task | Tier | " + " | ".join(order) + " |"
    sep = "|---|:--:|" + "|".join([":--:"] * len(order)) + "|"
    lines.append(header)
    lines.append(sep)
    for task, row in summary["matrix"].items():
        cells_md = " | ".join(f"{row[label][0]}/{row[label][1]}" for label in order)
        lines.append(f"| {task} | {summary['tiers'].get(task, '')} | {cells_md} |")
    lines.append("")

    # Cost / time-to-pass
    lines.append("## Cost & time-to-pass")
    lines.append("")
    lines.append("| Cell | Mean wall to pass (s) | Mean iters to first green | "
                 "Mean prompt+response chars |")
    lines.append("|---|--:|--:|--:|")
    for label in order:
        c = cells[label]
        lines.append(f"| {label} | {c['wall_to_pass']:.1f} | "
                     f"{c['green_to_pass']:.1f} | {c['mean_chars']:.0f} |")
    lines.append("")
    lines.append("> CI is the 95% Wilson score interval. Cost is reported as model "
                 "calls and prompt+response characters — the backends do not expose "
                 "token or dollar accounting, so chars are the available proxy.")
    lines.append("")
    return "\n".join(lines)


def generate_report(out_dir: Path) -> Path:
    payload = load_results(out_dir)
    summary = summarize(payload)
    md = render_markdown(payload, summary)
    path = out_dir / BENCH_REPORT_FILENAME
    path.write_text(md)
    return path
