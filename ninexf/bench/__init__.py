"""9xf bench — the falsifiable evaluation harness.

The core 9xf thesis is "a small local model plus hours of verified search
approaches big-model quality." Nothing in the harness measured that — and the
one signal it did produce (model-generated acceptance tests) was authored by the
same model being graded, so every "pass" was unfalsifiable.

This package fixes that. A benchmark task is a goal plus a *fixed external
oracle* (a human-authored test suite the solver never sees and never writes).
The runner drives a full loop per (task, model, config, seed) cell, then scores
the result against the oracle in a blind sandboxed subprocess. report.py
aggregates cells into pass-rates, pass@k, confidence intervals, and pairwise
effect sizes — the curve that proves or disproves the thesis.
"""

from __future__ import annotations

BENCH_RESULTS_FILENAME = "bench_results.json"
BENCH_REPORT_FILENAME = "BENCH.md"
ORACLE_SUITE_DIRNAME = "_oracle"  # transient dir the runner drops oracle tests into
