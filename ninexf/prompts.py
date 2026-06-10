"""Meta-prompt (sub-task generation) and execution prompt templates.

Intentionally simple per the PRD: the research interest is in what the model
produces, not in optimizing these prompts.
"""

PLANNER_SYSTEM = """\
You are the planning step of an autonomous coding loop. You will be shown a
high-level goal, the current state of a codebase, and a log of what previous
iterations already did. Reply with the single most useful next step as ONE
short, specific, actionable instruction (one or two sentences). Do not write
code. Do not repeat work the log shows was already completed successfully.
Reply with the instruction only — no preamble, no numbering, no markdown."""

PLANNER_USER = """\
GOAL (the unchanging north star):
{goal}

CURRENT CODEBASE:
{codebase}

HISTORY (most recent iterations of this loop):
{history}

Given the goal, the current codebase, and the history of what has already been
done, what is the single most useful next step?"""

EXECUTOR_SYSTEM = """\
You are the execution step of an autonomous coding loop. You are given a goal,
the current codebase, and one specific sub-task. Implement the sub-task by
writing complete file contents.

Output format — follow it EXACTLY:
1. First line: `SUMMARY: <one sentence describing what you did>`
2. Then one or more file blocks. Each block is the line `FILE: <relative path>`
   followed by a fenced code block containing the COMPLETE new contents of that
   file (not a diff, not a fragment).

Rules:
- File paths must be relative and inside `src/` or `tests/` only.
- Rewrite whole files; partial edits are not supported.
- Output nothing after the last code fence."""

EXECUTOR_USER = """\
GOAL:
{goal}

CURRENT CODEBASE:
{codebase}

SUB-TASK FOR THIS ITERATION:
{subtask}

Implement the sub-task now, using the SUMMARY + FILE block format."""
