"""Fixed external oracle for the `calculator` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")  # discovery runs from the project root (cwd)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestCalculator(unittest.TestCase):
    def setUp(self):
        try:
            import calculator
        except Exception as e:  # noqa: BLE001 - any import failure is a task failure
            self.fail(f"could not import src/calculator.py: {e}")
        self.calc = calculator

    def test_add(self):
        self.assertEqual(self.calc.add(2, 3), 5)
        self.assertEqual(self.calc.add(-1, 1), 0)

    def test_subtract(self):
        self.assertEqual(self.calc.subtract(10, 4), 6)
        self.assertEqual(self.calc.subtract(0, 5), -5)

    def test_multiply(self):
        self.assertEqual(self.calc.multiply(6, 7), 42)
        self.assertEqual(self.calc.multiply(0, 99), 0)

    def test_divide(self):
        self.assertAlmostEqual(self.calc.divide(9, 2), 4.5)
        self.assertAlmostEqual(self.calc.divide(8, 4), 2.0)

    def test_divide_by_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.calc.divide(1, 0)


if __name__ == "__main__":
    unittest.main()
