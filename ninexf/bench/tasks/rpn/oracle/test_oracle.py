"""Fixed external oracle for the `rpn` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestRPN(unittest.TestCase):
    def setUp(self):
        try:
            import rpn
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import src/rpn.py: {e}")
        self.fn = rpn.evaluate

    def test_basic(self):
        self.assertAlmostEqual(self.fn("3 4 +"), 7.0)
        self.assertAlmostEqual(self.fn("10 2 -"), 8.0)
        self.assertAlmostEqual(self.fn("6 7 *"), 42.0)
        self.assertAlmostEqual(self.fn("8 2 /"), 4.0)

    def test_nested(self):
        self.assertAlmostEqual(self.fn("5 1 2 + 4 * +"), 17.0)
        self.assertAlmostEqual(self.fn("2 3 4 * +"), 14.0)

    def test_malformed_raises(self):
        with self.assertRaises(ValueError):
            self.fn("3 +")          # too few operands
        with self.assertRaises(ValueError):
            self.fn("3 4 5 +")      # too many operands left over
        with self.assertRaises(ValueError):
            self.fn("3 4 %")        # unknown token


if __name__ == "__main__":
    unittest.main()
