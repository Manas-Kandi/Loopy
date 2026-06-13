"""Per-run file cache: read + AST-parse each file once, reuse until it changes.

Context building re-scores the whole codebase every iteration. The subtask
changes each time (so scores must be recomputed), but the *inputs* to scoring —
a file's text, its imports, its def/class names, its head tokens — only change
when the file changes. This cache memoizes that subtask-independent work, keyed
on (mtime, size) so a git restore or an edit invalidates exactly the touched
files. Over an 8-hour overnight run that turns thousands of redundant reads and
ast.parse calls into a handful.

The cache is duck-typed: consumers (relevance.score_files, context.build_snapshot)
call `.get(path)` and read fields off the result, so they need not import this
module — which keeps the dependency edge one-way (this imports relevance, not
the reverse).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from ninexf.relevance import HEAD_CHARS, _tokens


@dataclass
class CachedFile:
    text: str = ""
    n_chars: int = 0
    import_names: set[str] = field(default_factory=set)
    def_names: list[str] = field(default_factory=list)
    head_tokens: set[str] = field(default_factory=set)
    readable: bool = False     # False only when the file could not be read
    source_ok: bool = False    # True when the file parsed as Python


_UNREADABLE = CachedFile()


def _build(path: Path) -> CachedFile:
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return _UNREADABLE
    import_names: set[str] = set()
    def_names: list[str] = []
    source_ok = True
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        source_ok = False
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                import_names.add(node.module.split(".")[0])
        def_names = [n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return CachedFile(
        text=text, n_chars=len(text), import_names=import_names,
        def_names=def_names, head_tokens=_tokens(text[:HEAD_CHARS]),
        readable=True, source_ok=source_ok,
    )


class FileCache:
    """Memoizes CachedFile per path, invalidating on (mtime_ns, size) change."""

    def __init__(self) -> None:
        self._entries: dict[Path, tuple[tuple[int, int], CachedFile]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, path: Path) -> CachedFile:
        try:
            st = path.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            return _UNREADABLE
        cached = self._entries.get(path)
        if cached is not None and cached[0] == key:
            self.hits += 1
            return cached[1]
        self.misses += 1
        entry = _build(path)
        self._entries[path] = (key, entry)
        return entry
