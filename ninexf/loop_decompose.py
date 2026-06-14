"""DecomposeMixin: break the goal into TASKS.md + ACCEPTANCE.md (once per run)."""

from __future__ import annotations

from ninexf.loop_common import *  # noqa: F401,F403 - shared LoopRunner surface


class DecomposeMixin:
    def _needs_decompose(self) -> bool:
        if not self.config.decompose_enabled:
            return False
        if tasks_path(self.project_dir).exists():
            return False
        # one attempt per run dir: a logged decompose event means we already
        # tried and fell back to v0.2 planning — don't retry forever
        return not any(e.get("event") == "decompose" for e in read_entries(self.project_dir))

    def _run_decompose(self, iteration: int) -> LogEntry:
        """One model call breaking the goal into TASKS.md + ACCEPTANCE.md."""
        logger.info(f"[9xf] iter {iteration} (decompose) breaking the goal into tasks")
        write_state(self.project_dir, running=True, iteration=iteration, mode="decompose",
                    subtask="(decomposing goal)", ts=now_iso())
        append_activity(self.project_dir, "asking model to decompose the goal",
                        iteration=iteration, kind="model")
        rejections: list[str] = []
        errors: list[str] = []
        try:
            raw = self._complete("decompose", DECOMPOSE_SYSTEM, DECOMPOSE_USER.format(goal=self.goal))
            append_activity(self.project_dir, "parsing decomposition output",
                            iteration=iteration)
            task_texts, criteria = parse_decomposition(raw)
            task_texts, criteria, rejections = sanitize_decomposition(
                self.goal, task_texts, criteria)
            if rejections and len(task_texts) < 2:
                retry_user = DECOMPOSE_USER.format(goal=self.goal) + DECOMPOSE_RETRY_NOTE.format(
                    rejections="\n".join(f"- {r}" for r in rejections[:8]))
                raw = self._complete("decompose_retry", DECOMPOSE_SYSTEM, retry_user)
                retry_tasks, retry_criteria = parse_decomposition(raw)
                task_texts, criteria, retry_rejections = sanitize_decomposition(
                    self.goal, retry_tasks, retry_criteria)
                rejections.extend(retry_rejections)
        except BackendError as e:
            if not getattr(e, "retryable", True):
                raise
            task_texts, criteria = [], []
            errors.append(f"decomposition backend failed; used fallback roadmap: {e}")

        if rejections:
            errors.extend(f"decomposition rejected {r}" for r in rejections[:8])
        if len(task_texts) < 2:
            fallback_tasks, fallback_criteria = fallback_decomposition(self.goal)
            save_tasks(self.project_dir,
                       TaskList(tasks=[Task(num=i, text=t)
                                       for i, t in enumerate(fallback_tasks, start=1)]))
            save_criteria(self.project_dir, fallback_criteria)
            save_contract(self.project_dir, self.goal, fallback_tasks, fallback_criteria)
            errors.append(f"decomposition produced only {len(task_texts)} task(s); "
                          "used deterministic fallback roadmap")
            append_activity(
                self.project_dir,
                f"created fallback TASKS.md, ACCEPTANCE.md, and CONTRACT.md ({len(fallback_tasks)} tasks)",
                iteration=iteration,
                kind="write",
            )
            summary = ("decomposition failed; installed deterministic fallback roadmap "
                       f"with {len(fallback_tasks)} tasks and {len(fallback_criteria)} criteria")
        else:
            save_tasks(self.project_dir,
                       TaskList(tasks=[Task(num=i, text=t)
                                       for i, t in enumerate(task_texts, start=1)]))
            save_criteria(self.project_dir, criteria)
            save_contract(self.project_dir, self.goal, task_texts, criteria)
            append_activity(self.project_dir,
                            f"created TASKS.md, ACCEPTANCE.md, and CONTRACT.md ({len(task_texts)} tasks)",
                            iteration=iteration, kind="write")
            summary = (f"decomposed goal into {len(task_texts)} tasks "
                       f"and {len(criteria)} acceptance criteria")
        logger.info(f"[9xf]   {summary}")

        commit_hash = ""
        if has_changes(self.project_dir):
            append_activity(self.project_dir, "committing decomposition result",
                            iteration=iteration, kind="git")
            commit_hash = commit_all(self.project_dir, f"[iter {iteration}] (decompose) {summary}")
        entry = LogEntry(
            iteration=iteration, timestamp=now_iso(), subtask="(decompose goal)",
            summary=summary, errors=errors, commit=commit_hash,
            event="decompose", mode="decompose",
            tasks_total=len(task_texts) if len(task_texts) >= 2 else 0,
            model_calls=self._take_model_calls(),
            context_overflow=self.backend.take_overflow(),
        )
        append_entry(self.project_dir, entry)
        write_state(self.project_dir, running=True, iteration=iteration, mode="decompose",
                    subtask=summary, ts=now_iso())
        if has_changes(self.project_dir):
            commit_all(self.project_dir, f"[iter {iteration}] log entry")
        return entry
