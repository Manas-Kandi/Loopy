"""Fixed external oracle for the `anagram_groups` task. Never shown to the solver.

Group order and within-group order are not constrained, so the oracle compares
the set of groups (as frozensets) to stay robust to ordering choices."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _normalize(groups):
    return {frozenset(g) for g in groups}


class TestAnagramGroups(unittest.TestCase):
    def setUp(self):
        try:
            from anagram_groups import group_anagrams
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import group_anagrams from src/anagram_groups.py: {e}")
        self.fn = group_anagrams

    def test_empty(self):
        self.assertEqual(self.fn([]), [])

    def test_classic(self):
        result = self.fn(["eat", "tea", "tan", "ate", "nat", "bat"])
        self.assertEqual(
            _normalize(result),
            {frozenset({"eat", "tea", "ate"}), frozenset({"tan", "nat"}),
             frozenset({"bat"})},
        )
        # every input word appears exactly once across the groups
        self.assertEqual(sum(len(g) for g in result), 6)

    def test_no_anagrams(self):
        self.assertEqual(_normalize(self.fn(["abc", "def", "ghi"])),
                         {frozenset({"abc"}), frozenset({"def"}), frozenset({"ghi"})})


if __name__ == "__main__":
    unittest.main()
