"""Parse the executor's SUMMARY + FILE-block output format.

Local models are unreliable at strict JSON, so the contract is plain text:

    SUMMARY: did a thing
    FILE: src/foo.py
    ```python
    ...complete file contents...
    ```

The parser is deliberately forgiving about whitespace, fence language tags,
and stray prose between blocks — malformed output is itself research data,
so parse failures are reported, not crashed on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FILE_BLOCK_RE = re.compile(
    r"FILE:\s*(?P<path>[^\n`]+?)\s*\n+\s*```[a-zA-Z0-9_+-]*\n(?P<body>.*?)\n?```",
    re.DOTALL,
)
SUMMARY_RE = re.compile(r"SUMMARY:\s*(?P<summary>[^\n]+)")


@dataclass
class ParsedOutput:
    summary: str = ""
    files: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def parse_executor_output(text: str) -> ParsedOutput:
    out = ParsedOutput()

    m = SUMMARY_RE.search(text)
    out.summary = m.group("summary").strip() if m else ""
    if not out.summary:
        out.problems.append("no SUMMARY line found")

    for m in FILE_BLOCK_RE.finditer(text):
        path = m.group("path").strip().strip("'\"")
        body = m.group("body")
        if path in out.files:
            out.problems.append(f"duplicate FILE block for {path}; last one wins")
        out.files[path] = body + ("\n" if not body.endswith("\n") else "")

    if not out.files:
        out.problems.append("no FILE blocks found in model output")

    return out
