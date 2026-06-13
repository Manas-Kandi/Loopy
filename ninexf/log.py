"""Logging backbone for the loop's operational output.

v0.6 and earlier scattered bare print() through loop.py — no levels, no way to
quiet an overnight run or turn up detail for a failing one. This wraps stdlib
logging with a logger whose default format is just the message, so the existing
"[9xf] ..." lines render byte-identically; the difference is that callers now go
through one configurable channel. The structured research log (loop_log.jsonl
via looplog.append_entry) is unchanged — that's the durable artifact; this is the
human-facing console stream.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("ninexf")


def configure(*, verbose: bool = False, quiet: bool = False) -> None:
    """Set the console level. quiet -> warnings only; verbose -> debug; else info.
    Idempotent: safe to call from the CLI and harmless when never called (a
    sensible default is installed on import for library/test use)."""
    level = logging.WARNING if quiet else logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.propagate = False


configure()  # default INFO console so direct LoopRunner use prints as before
