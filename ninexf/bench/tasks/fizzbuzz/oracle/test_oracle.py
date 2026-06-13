"""Fixed external oracle for the `fizzbuzz` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestFizzBuzz(unittest.TestCase):
    def setUp(self):
        try:
            import fizzbuzz
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import src/fizzbuzz.py: {e}")
        self.fn = fizzbuzz.fizzbuzz

    def test_empty(self):
        self.assertEqual(self.fn(0), [])

    def test_first_fifteen(self):
        self.assertEqual(self.fn(15), [
            "1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz",
            "11", "Fizz", "13", "14", "FizzBuzz",
        ])

    def test_length(self):
        self.assertEqual(len(self.fn(30)), 30)
        self.assertEqual(self.fn(30)[29], "FizzBuzz")


if __name__ == "__main__":
    unittest.main()
