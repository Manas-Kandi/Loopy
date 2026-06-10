"""The loop: read state -> self-generate sub-task -> execute -> validate -> commit -> log.

Failed iterations are still committed (failed attempts are research data).
Shutdown paths (STOP file, Ctrl+C, iteration cap, repeated backend failure)
all go through the same clean-shutdown sequence: commit, log, exit.
"""

from __future__ import annotations

import signal
import time
from pathlib import Path

from ninexf import GOAL_FILENAME, STOP_FILENAME
from ninexf.backends import Backend, BackendError, make_backend
from ninexf.config import Config
from ninexf.context import history_for_context, snapshot_codebase
from ninexf.gitops import commit_all, has_changes
from ninexf.looplog import LogEntry, append_entry, last_iteration_number, now_iso
from ninexf.parser import parse_executor_output
from ninexf.prompts import EXECUTOR_SYSTEM, EXECUTOR_USER, PLANNER_SYSTEM, PLANNER_USER
from ninexf.sandbox import ContainmentViolation, safe_write
from ninexf.validate import validate

MAX_CONSECUTIVE_BACKEND_FAILURES = 3


class LoopRunner:
    def __init__(self, project_dir: Path, config: Config):
        self.project_dir = project_dir
        self.config = config
        self.backend: Backend = make_backend(config)
        self.goal = (project_dir / GOAL_FILENAME).read_text().strip()
        self._interrupted = False

    # -- shutdown plumbing ----------------------------------------------------

    def _install_sigint(self):
        def handler(signum, frame):
            if self._interrupted:  # second Ctrl+C: give up politely
                raise KeyboardInterrupt
            self._interrupted = True
            print("\n[9xf] Ctrl+C received — finishing this iteration, then shutting down cleanly.")

        signal.signal(signal.SIGINT, handler)

    def _stop_requested(self) -> str | None:
        if (self.project_dir / STOP_FILENAME).exists():
            return "STOP file detected"
        if self._interrupted:
            return "interrupted by Ctrl+C"
        return None

    def _clean_shutdown(self, iteration: int, reason: str):
        print(f"[9xf] shutting down: {reason}")
        append_entry(self.project_dir, LogEntry(
            iteration=iteration, timestamp=now_iso(), subtask="", summary=reason,
            event="shutdown",
        ))
        try:
            if has_changes(self.project_dir):
                commit_all(self.project_dir, f"9xf shutdown: {reason}")
            else:
                commit_all(self.project_dir, f"9xf shutdown: {reason}", allow_empty=True)
        except Exception as e:
            print(f"[9xf] warning: shutdown commit failed: {e}")

    # -- one iteration ---------------------------------------------------------

    def run_iteration(self, iteration: int) -> LogEntry:
        cfg = self.config
        codebase = snapshot_codebase(self.project_dir, cfg.context_char_budget)
        history = history_for_context(self.project_dir, cfg.history_entries_in_context)

        # 1. self-generate the sub-task
        subtask = self.backend.complete(
            PLANNER_SYSTEM,
            PLANNER_USER.format(goal=self.goal, codebase=codebase, history=history),
        ).strip().splitlines()[0][:500]
        print(f"[9xf] iter {iteration} subtask: {subtask}")

        # 2. execute it
        raw = self.backend.complete(
            EXECUTOR_SYSTEM,
            EXECUTOR_USER.format(goal=self.goal, codebase=codebase, subtask=subtask),
        )
        parsed = parse_executor_output(raw)

        errors = list(parsed.problems)
        written: list[Path] = []
        for rel_path, content in parsed.files.items():
            try:
                written.append(safe_write(self.project_dir, rel_path, content))
            except ContainmentViolation as v:
                errors.append(str(v))
                append_entry(self.project_dir, LogEntry(
                    iteration=iteration, timestamp=now_iso(), subtask=subtask,
                    summary=f"containment violation: {v.requested!r}", event="violation",
                ))

        # 3. validate
        if written:
            result = validate(self.project_dir, written, cfg.validation_timeout, cfg.allow_network)
            errors.extend(result.errors)
            validation_passed, validation_detail = result.passed, result.detail
        else:
            validation_passed, validation_detail = False, "nothing written"

        # 4. commit (failed attempts included — research data)
        status = "ok" if validation_passed and not errors else "failed"
        commit_msg = f"[iter {iteration}] ({status}) {subtask}\n\n{parsed.summary}"
        commit_hash = ""
        if has_changes(self.project_dir):
            commit_hash = commit_all(self.project_dir, commit_msg)

        entry = LogEntry(
            iteration=iteration,
            timestamp=now_iso(),
            subtask=subtask,
            summary=parsed.summary,
            files_written=[str(p.relative_to(self.project_dir)) for p in written],
            validation_passed=validation_passed,
            validation_detail=validation_detail,
            errors=errors,
            commit=commit_hash,
        )
        append_entry(self.project_dir, entry)

        # commit the log line itself so git history and log stay in lockstep
        if has_changes(self.project_dir):
            commit_all(self.project_dir, f"[iter {iteration}] log entry")
        return entry

    # -- the loop ----------------------------------------------------------------

    def run(self, max_iterations: int | None = None, delay: float | None = None):
        cfg = self.config
        cap = max_iterations if max_iterations is not None else cfg.max_iterations
        sleep_s = delay if delay is not None else cfg.delay_seconds
        self._install_sigint()

        start = last_iteration_number(self.project_dir)
        append_entry(self.project_dir, LogEntry(
            iteration=start, timestamp=now_iso(), subtask="",
            summary=f"run started (model={cfg.model}, cap={cap}, delay={sleep_s}s)",
            event="startup",
        ))
        print(f"[9xf] goal: {self.goal}")
        print(f"[9xf] model: {cfg.model} | starting at iteration {start + 1}, cap {cap}")

        backend_failures = 0
        iteration = start
        while iteration - start < cap:
            reason = self._stop_requested()
            if reason:
                self._clean_shutdown(iteration, reason)
                return

            iteration += 1
            try:
                entry = self.run_iteration(iteration)
                backend_failures = 0
                mark = "✓" if entry.validation_passed else "✗"
                print(f"[9xf] iter {iteration} {mark} {entry.summary or '(no summary)'}"
                      f"  [{entry.commit or 'no commit'}]")
            except BackendError as e:
                backend_failures += 1
                print(f"[9xf] iter {iteration} backend error ({backend_failures}/"
                      f"{MAX_CONSECUTIVE_BACKEND_FAILURES}): {e}")
                append_entry(self.project_dir, LogEntry(
                    iteration=iteration, timestamp=now_iso(), subtask="",
                    summary="backend error", errors=[str(e)], validation_passed=False,
                ))
                if backend_failures >= MAX_CONSECUTIVE_BACKEND_FAILURES:
                    self._clean_shutdown(iteration, "too many consecutive backend failures")
                    return

            reason = self._stop_requested()
            if reason:
                self._clean_shutdown(iteration, reason)
                return
            if iteration - start < cap:
                time.sleep(sleep_s)

        self._clean_shutdown(iteration, f"iteration cap reached ({cap})")
