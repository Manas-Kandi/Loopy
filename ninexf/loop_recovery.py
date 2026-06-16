"""RecoveryMixin: auto-revert after failure streaks, and branch-and-explore."""

from __future__ import annotations

from ninexf.loop_common import *  # noqa: F401,F403 - shared LoopRunner surface


class RecoveryMixin:
    # -- auto-revert (v0.3) -------------------------------------------------------

    def _maybe_revert(self, iteration: int) -> None:
        """After N consecutive failures, restore src/tests/tools to the last
        green commit (history stays linear — restore + new commit, no reset).
        Repeated reverts to the same commit defer the failing task instead,
        so the loop can't ping-pong between revert and the same broken fix."""
        cfg = self.config
        if cfg.revert_after_failures <= 0:
            return
        entries = read_entries(self.project_dir)
        iters = [e for e in entries if e.get("event") == "iteration"]
        # a revert (or deferral) event resets the failure streak: only count
        # failures from that iteration onward, so we don't re-trigger every loop
        boundary = max((e.get("iteration", 0) for e in entries
                        if e.get("event") == "revert"), default=0)
        streak = []
        for e in reversed(iters):
            if e.get("validation_passed") or e.get("iteration", 0) < boundary:
                break
            streak.append(e)
        if len(streak) < cfg.revert_after_failures:
            return
        green = next((e for e in reversed(iters)
                      if e.get("validation_passed") and e.get("commit")), None)
        if green is None:
            return  # nothing green to go back to
        target = green["commit"]

        reverts_here = sum(1 for e in entries
                           if e.get("event") == "revert" and e.get("reverted_to") == target)
        if reverts_here >= MAX_REVERTS_TO_SAME_COMMIT:
            # reverting again won't help — defer the task being ground on instead
            task_id = next((e.get("task_id", 0) for e in streak if e.get("task_id")), 0)
            if not task_id:
                tl = load_tasks(self.project_dir)
                task_id = next((t.num for t in tl.tasks
                                if t.status == STATUS_IN_PROGRESS), 0)
            if task_id:
                mark_status(self.project_dir, task_id, STATUS_DEFERRED)
                logger.info(f"[9xf]   revert limit hit — deferring task T{task_id} instead")
                append_entry(self.project_dir, LogEntry(
                    iteration=iteration, timestamp=now_iso(), subtask="",
                    summary=f"revert limit reached for {target}; deferred task T{task_id}",
                    event="revert", reverted_to="",
                ))
                if has_changes(self.project_dir):
                    commit_all(self.project_dir,
                               f"[iter {iteration}] deferred T{task_id} after repeated reverts")
            return

        first_bad = streak[-1]["iteration"]
        logger.info(f"[9xf]   auto-revert: {len(streak)} consecutive failures — "
              f"restoring {'/'.join(WRITABLE_DIRS)} to {target}")
        restore_paths(self.project_dir, target, WRITABLE_DIRS)
        summary = (f"auto-revert to {target} after {len(streak)} consecutive failures "
                   f"(iterations {first_bad}–{streak[0]['iteration']} discarded)")
        if cfg.notes_enabled:
            append_notes(self.project_dir, iteration,
                         [f"HARNESS: reverted to {target}; the approach of iterations "
                          f"{first_bad}–{streak[0]['iteration']} failed — try differently"],
                         cfg.notes_max_lines)
        commit_hash = ""
        if has_changes(self.project_dir):
            commit_hash = commit_all(self.project_dir, f"[iter {iteration}] (revert) {summary}")
        append_entry(self.project_dir, LogEntry(
            iteration=iteration, timestamp=now_iso(), subtask="", summary=summary,
            commit=commit_hash, event="revert", reverted_to=target,
        ))

    # -- branch-and-explore (v0.3) -------------------------------------------------

    def _maybe_explore(self, iteration: int) -> LogEntry | None:
        """Hard-stuck: try two genuinely different approaches on git branches,
        validate both, adopt the winner on the main branch by file checkout.
        Returns the explore LogEntry (consuming this iteration) or None."""
        cfg = self.config
        if not cfg.explore_enabled:
            return None
        entries = read_entries(self.project_dir)
        if count_explores(entries) >= cfg.max_explores_per_run:
            return None
        if not should_explore(entries, cfg.explore_after_stuck):
            return None

        logger.info(f"[9xf] iter {iteration} (explore) hard-stuck — trying two approaches on branches")
        write_state(self.project_dir, running=True, iteration=iteration, mode="explore",
                    subtask="(exploring two approaches)", ts=now_iso())
        prev_entries = [e for e in entries if e.get("event") == "iteration"]
        plan_query = " ".join(t.text for t in load_tasks(self.project_dir).open_tasks())
        codebase = snapshot_codebase(self.project_dir, cfg.snapshot_budget,
                                     subtask=plan_query, entries=prev_entries,
                                     strategy=cfg.context_strategy, cache=self._file_cache)
        history = history_for_context(self.project_dir, cfg.history_entries_in_context)
        tools = tools_for_prompt(self.project_dir) if cfg.tools_enabled else "(tools disabled)"
        base = self._planner_base("build", codebase, history, tools)

        plan_a = self._complete(
            "explore_plan_a",
            PLANNER_SYSTEM, base + EXPLORE_NUDGE_A).strip().splitlines()[0][:500]
        plan_b = self._complete(
            "explore_plan_b",
            PLANNER_SYSTEM, base + EXPLORE_NUDGE_B.format(plan_a=plan_a)
        ).strip().splitlines()[0][:500]

        home = current_branch(self.project_dir)
        results: dict[str, dict] = {}
        for label, plan in (("a", plan_a), ("b", plan_b)):
            branch = f"explore-i{iteration}-{label}"
            create_branch(self.project_dir, branch)
            exec_codebase, _ = build_snapshot(
                self.project_dir, cfg.snapshot_budget, subtask=plan,
                entries=prev_entries, strategy=cfg.context_strategy, cache=self._file_cache)
            notes = notes_for_prompt(self.project_dir) if cfg.notes_enabled else ""
            feedback = user_feedback_for_prompt(self.project_dir)
            contract = contract_for_prompt(self.project_dir)
            contract_section = CONTRACT_SECTION.format(contract=contract) if contract else ""
            feedback_section = FEEDBACK_SECTION.format(feedback=feedback) if feedback else ""
            executor_user = EXECUTOR_USER.format(
                goal=self.goal, codebase=exec_codebase, subtask=plan, tools=tools,
                contract_section=contract_section,
                feedback_section=feedback_section,
                notes_section=NOTES_SECTION.format(notes=notes) if notes else "")
            ev = self._execute_once(iteration, plan, executor_user, None,
                                    log_violations=False, purpose=f"explore_executor_{label}")
            acc, _ = (run_acceptance(self.project_dir, cfg.validation_timeout,
                                     cfg.allow_network) if ev.written else (None, 0))
            if has_changes(self.project_dir):
                commit_all(self.project_dir, f"[iter {iteration}] (explore/{label}) {plan}")
            results[label] = {
                "plan": plan, "branch": branch, "summary": ev.parsed.summary,
                "passed": ev.validation_passed and not ev.errors,
                "acceptance_passed": acc, "tests_ran": ev.tests_ran,
                "errors_n": len(ev.errors),
            }
            logger.info(f"[9xf]   approach {label.upper()}: "
                  f"{'ok' if results[label]['passed'] else 'FAILED'} — {plan[:80]}")
            checkout_branch(self.project_dir, home)

        def _key(r: dict) -> tuple:
            return (r["passed"], 1 if r["acceptance_passed"] else 0,
                    r["tests_ran"], -r["errors_n"])

        winner = "a" if _key(results["a"]) >= _key(results["b"]) else "b"
        loser = "b" if winner == "a" else "a"
        restore_paths(self.project_dir, results[winner]["branch"], WRITABLE_DIRS)
        rename_branch(self.project_dir, results[loser]["branch"],
                      results[loser]["branch"] + "-rejected")
        summary = (f"explore: adopted approach {winner.upper()} "
                   f"({results[winner]['plan'][:100]}) over {loser.upper()}")
        logger.info(f"[9xf]   {summary}")
        if cfg.notes_enabled:
            append_notes(self.project_dir, iteration,
                         [f"HARNESS: explored two approaches; adopted {winner.upper()} "
                          f"({results[winner]['plan'][:100]})"], cfg.notes_max_lines)
        commit_hash = ""
        if has_changes(self.project_dir):
            commit_hash = commit_all(self.project_dir, f"[iter {iteration}] (explore) {summary}")
        entry = LogEntry(
            iteration=iteration, timestamp=now_iso(),
            subtask=results[winner]["plan"], summary=summary,
            validation_passed=results[winner]["passed"], commit=commit_hash,
            event="explore", mode="explore",
            explore={**results, "winner": winner},
            model_calls=self._take_model_calls(),
            context_overflow=self.backend.take_overflow(),
        )
        append_entry(self.project_dir, entry)
        write_state(self.project_dir, running=True, iteration=iteration, mode="explore",
                    subtask=summary, validation_passed=results[winner]["passed"],
                    ts=now_iso())
        if has_changes(self.project_dir):
            commit_all(self.project_dir, f"[iter {iteration}] log entry")
        return entry
