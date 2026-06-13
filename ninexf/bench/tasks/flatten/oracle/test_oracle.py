"""Fixed external oracle for the `flatten` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestFlatten(unittest.TestCase):
    def setUp(self):
        try:
            from flatten import flatten
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import flatten from src/flatten.py: {e}")
        self.fn = flatten

    def test_empty(self):
        self.assertEqual(self.fn({}), {})

    def test_flat_passthrough(self):
        self.assertEqual(self.fn({"a": 1, "b": 2}), {"a": 1, "b": 2})

    def test_nested(self):
        self.assertEqual(
            self.fn({"a": 1, "b": {"c": 2, "d": {"e": 3}}}),
            {"a": 1, "b.c": 2, "b.d.e": 3},
        )

    def test_custom_separator(self):
        self.assertEqual(self.fn({"a": {"b": 1}}, sep="/"), {"a/b": 1})

    def test_lists_kept_as_values(self):
        self.assertEqual(self.fn({"a": {"b": [1, 2, 3]}}), {"a.b": [1, 2, 3]})


if __name__ == "__main__":
    unittest.main()
