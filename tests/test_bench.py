"""Bench harness self-test: drive the smoke experiment against the mock backend
and assert the fixed external oracle scores both directions correctly, plus the
results JSON / BENCH.md are produced. No real model required.

Importing tests.helpers isolates the run registry to a temp dir (side effect)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import tests.helpers  # noqa: F401 - sets NINEXF_REGISTRY_DIR on import
from ninexf.bench import BENCH_REPORT_FILENAME, BENCH_RESULTS_FILENAME
from ninexf.bench.report import cohens_h, generate_report, summarize, wilson_interval
from ninexf.bench.runner import run_experiment
from ninexf.bench.spec import ExperimentSpec, all_task_names


class TestSmokeExperiment(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="9xf-bench-")).resolve()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_oracle_scores_both_directions(self):
        exp = ExperimentSpec.load("smoke")
        results = run_experiment(exp, self.out, progress=lambda *_: None)

        by_task = {r.task: r for r in results}
        self.assertIn("greeting", by_task)
        self.assertIn("calculator", by_task)

        # mock 'finisher' always builds the greeting -> greeting oracle PASSES
        self.assertTrue(by_task["greeting"].oracle_passed,
                        by_task["greeting"].oracle_detail)
        self.assertGreater(by_task["greeting"].oracle_tests_ran, 0)
        self.assertEqual(by_task["greeting"].error, "")

        # ...but it never builds a calculator -> calculator oracle FAILS,
        # even though the loop's own verify_done declared the goal complete.
        self.assertFalse(by_task["calculator"].oracle_passed)
        self.assertTrue(by_task["calculator"].finished,
                        "the loop self-reports done — the external oracle catches it")

    def test_results_json_and_report_written(self):
        exp = ExperimentSpec.load("smoke")
        run_experiment(exp, self.out, progress=lambda *_: None)

        results_path = self.out / BENCH_RESULTS_FILENAME
        self.assertTrue(results_path.exists())
        payload = json.loads(results_path.read_text())
        self.assertEqual(payload["experiment"], "smoke")
        self.assertEqual(len(payload["results"]), 2)
        for r in payload["results"]:
            for key in ("oracle_passed", "iterations", "model_calls", "wall_clock_s"):
                self.assertIn(key, r)

        report_path = generate_report(self.out)
        self.assertEqual(report_path.name, BENCH_REPORT_FILENAME)
        text = report_path.read_text()
        self.assertIn("Benchmark: smoke", text)
        self.assertIn("Pass rates", text)
        self.assertIn("Per-task results", text)


class TestStats(unittest.TestCase):
    def test_wilson_interval_bounds(self):
        lo, hi = wilson_interval(5, 10)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)
        self.assertEqual(wilson_interval(0, 0), (0.0, 0.0))
        # all-pass: upper bound is 1.0, lower bound below 1
        lo, hi = wilson_interval(10, 10)
        self.assertLessEqual(hi, 1.0)
        self.assertLess(lo, 1.0)

    def test_cohens_h_zero_when_equal(self):
        self.assertAlmostEqual(cohens_h(0.5, 0.5), 0.0)
        self.assertGreater(cohens_h(0.9, 0.5), 0.0)  # higher proportion -> positive

    def test_summarize_groups_by_cell(self):
        payload = {
            "experiment": "x", "seeds": 2, "reference_cell": "b",
            "results": [
                _row("a", "t1", 0, True), _row("a", "t1", 1, False),
                _row("b", "t1", 0, True), _row("b", "t1", 1, True),
            ],
        }
        s = summarize(payload)
        self.assertEqual(s["cells"]["a"]["passes"], 1)
        self.assertEqual(s["cells"]["b"]["passes"], 2)
        self.assertEqual(s["cells"]["a"]["pass_at_k"], 1.0)  # solved at least once
        self.assertTrue(any(p["cell"] == "a" for p in s["pairwise"]))


class TestTaskSuite(unittest.TestCase):
    def test_every_task_has_goal_and_oracle(self):
        names = all_task_names()
        self.assertIn("greeting", names)
        self.assertIn("calculator", names)
        from ninexf.bench.spec import load_task
        for name in names:
            task = load_task(name)  # raises if goal.txt or oracle missing
            self.assertTrue(task.goal)


def _row(cell: str, task: str, seed: int, passed: bool) -> dict:
    return {
        "experiment": "x", "cell": cell, "model": "mock/finisher", "preset": None,
        "task": task, "tier": "easy", "seed": seed, "oracle_passed": passed,
        "oracle_tests_ran": 2, "oracle_detail": "", "finished": True,
        "iterations": 5, "first_green_iteration": 2 if passed else None,
        "wall_clock_s": 1.0, "model_calls": 10, "prompt_chars": 100,
        "response_chars": 50, "model_latency_s": 0.0, "error": "",
    }


if __name__ == "__main__":
    unittest.main()
