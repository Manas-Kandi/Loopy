"""Track 2: the per-run file cache must (a) avoid re-reading/re-parsing
unchanged files, (b) invalidate when a file changes, and (c) produce byte-for-byte
identical context to the uncached path — it's a speedup, not a behavior change."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from ninexf.context import build_snapshot
from ninexf.filecache import FileCache
from ninexf.relevance import score_files


class TestFileCache(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="9xf-fc-")).resolve()
        (self.d / "src").mkdir()
        (self.d / "src" / "main.py").write_text(
            "import os\n\ndef main():\n    return run()\n")
        (self.d / "src" / "run.py").write_text(
            "import sys\n\ndef run():\n    return 1\n")
        (self.d / "tests").mkdir()
        (self.d / "tests" / "test_main.py").write_text(
            "import unittest\nfrom src.main import main\n")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _candidates(self):
        files = sorted((self.d / "src").glob("*.py"))
        return [(p, str(p.relative_to(self.d))) for p in files]

    def test_hit_avoids_recompute(self):
        cache = FileCache()
        cands = self._candidates()
        for path, _ in cands:
            cache.get(path)
        self.assertEqual(cache.misses, len(cands))
        self.assertEqual(cache.hits, 0)
        # second pass: every file unchanged -> all hits, no new builds (no re-parse)
        first = {p: cache.get(p) for p, _ in cands}
        self.assertEqual(cache.misses, len(cands))           # no new misses
        self.assertEqual(cache.hits, len(cands))
        # identity: a hit returns the very same cached object, proving no rebuild
        for p, _ in cands:
            self.assertIs(cache.get(p), first[p])

    def test_change_invalidates(self):
        cache = FileCache()
        target = self.d / "src" / "run.py"
        before = cache.get(target)
        cache.get(target)  # hit
        target.write_text("import sys\n\ndef run():\n    return 999  # changed\n")
        after = cache.get(target)
        self.assertIsNot(after, before, "changed file should rebuild")
        self.assertIn("999", after.text)

    def test_parsed_fields(self):
        cf = FileCache().get(self.d / "src" / "main.py")
        self.assertTrue(cf.readable)
        self.assertTrue(cf.source_ok)
        self.assertIn("os", cf.import_names)
        self.assertIn("main", cf.def_names)

    def test_scores_identical_cached_vs_uncached(self):
        cands = self._candidates()
        subtask = "fix the run function in src/run.py"
        plain = [(s.rel, round(s.score, 6)) for s in score_files(cands, subtask, [])]
        cached = [(s.rel, round(s.score, 6))
                  for s in score_files(cands, subtask, [], cache=FileCache())]
        self.assertEqual(plain, cached)

    def test_snapshot_identical_cached_vs_uncached(self):
        kwargs = dict(char_budget=10000, subtask="work on src/main.py",
                      entries=[], strategy="relevance")
        plain, plain_inc = build_snapshot(self.d, **kwargs)
        cached, cached_inc = build_snapshot(self.d, cache=FileCache(), **kwargs)
        self.assertEqual(plain, cached)
        self.assertEqual(plain_inc, cached_inc)


if __name__ == "__main__":
    unittest.main()
