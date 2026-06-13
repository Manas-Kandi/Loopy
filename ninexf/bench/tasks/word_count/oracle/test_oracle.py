"""Fixed external oracle for the `word_count` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestWordCount(unittest.TestCase):
    def setUp(self):
        try:
            import word_count
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import src/word_count.py: {e}")
        self.fn = word_count.word_frequencies

    def test_empty(self):
        self.assertEqual(self.fn(""), {})

    def test_case_insensitive(self):
        self.assertEqual(self.fn("The cat the CAT."), {"the": 2, "cat": 2})

    def test_punctuation_and_digits(self):
        self.assertEqual(
            self.fn("a-b a_b a1 a1"),
            {"a": 2, "b": 2, "a1": 2},
        )


if __name__ == "__main__":
    unittest.main()
