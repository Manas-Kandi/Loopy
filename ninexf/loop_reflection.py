"""ReflectionMixin: decide when to reflect, parse LEARN/AVOID/TRY notes, reflect."""

from __future__ import annotations

from ninexf.loop_common import *  # noqa: F401,F403 - shared LoopRunner surface


class ReflectionMixin:
    def _reflection_due(
        self,
        iteration: int,
        *,
        failed: bool,
        regression: bool,
        stuck_signals: list[str],
        parse_warnings: list[str],
        critic_verdict: str,
    ) -> bool:
        cfg = self.config
        if not (cfg.notes_enabled and cfg.reflection_enabled):
            return False
        if failed or regression or stuck_signals or parse_warnings:
            return True
        if critic_verdict == "REVISE":
            return True
        return cfg.reflection_every > 0 and iteration % cfg.reflection_every == 0

    def _parse_reflection_notes(self, raw: str, existing_notes: str) -> list[str]:
        existing = existing_notes.lower()
        notes: list[str] = []
        seen: set[str] = set()
        for line in raw.splitlines():
            m = REFLECTION_LINE_RE.match(line.strip())
            if not m:
                continue
            label = line.split(":", 1)[0].upper()
            text = m.group("text").strip()
            if not text:
                continue
            note = f"{label}: {text}"
            key = re.sub(r"\s+", " ", note.lower())
            if key in seen or key in existing:
                continue
            seen.add(key)
            notes.append(note[:300])
            if len(notes) >= self.config.reflection_max_notes:
                break
        return notes

    def _reflect(
        self,
        iteration: int,
        *,
        mode: str,
        subtask: str,
        outcome: "ExecOutcome",
        files_written: list[str],
        validation_passed: bool,
        errors: list[str],
        regression: bool,
        stuck_signals: list[str],
        critic_verdict: str,
        diagnosis: str,
        codebase: str,
        history: str,
    ) -> list[str]:
        append_activity(self.project_dir, "reflecting on recent evidence",
                        iteration=iteration, kind="reflection")
        notes = notes_for_prompt(self.project_dir) if self.config.notes_enabled else ""
        try:
            raw = self._complete(
                "reflection",
                REFLECTION_SYSTEM,
                REFLECTION_USER.format(
                    goal=self.goal,
                    contract=contract_for_prompt(self.project_dir) or "(none)",
                    codebase=codebase[: self.config.snapshot_budget],
                    history=history,
                    mode=mode,
                    subtask=subtask,
                    summary=outcome.parsed.summary,
                    files=", ".join(files_written) or "(none)",
                    validation_passed=validation_passed,
                    validation_detail=outcome.validation_detail,
                    errors="; ".join(str(e) for e in errors)[:1200] or "(none)",
                    parse_warnings="; ".join(outcome.parse_warnings) or "(none)",
                    regression=regression,
                    stuck_signals=", ".join(stuck_signals) or "(none)",
                    diagnosis=diagnosis or "(none)",
                    notes=notes or "(none)",
                ),
            )
        except BackendError as e:
            append_activity(self.project_dir, f"reflection skipped: {e}",
                            iteration=iteration, kind="error")
            return []
        learned = self._parse_reflection_notes(raw, notes)
        if learned:
            append_activity(self.project_dir, f"learned {len(learned)} prompt note(s)",
                            iteration=iteration, kind="reflection")
        return learned
