"""Fixed external oracle for the `roman` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

CASES = [(1, "I"), (4, "IV"), (9, "IX"), (40, "XL"), (90, "XC"),
         (400, "CD"), (900, "CM"), (1994, "MCMXCIV"), (3999, "MMMCMXCIX")]


class TestRoman(unittest.TestCase):
    def setUp(self):
        try:
            import roman
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import src/roman.py: {e}")
        self.r = roman

    def test_to_roman(self):
        for n, s in CASES:
            self.assertEqual(self.r.to_roman(n), s, f"to_roman({n})")

    def test_from_roman(self):
        for n, s in CASES:
            self.assertEqual(self.r.from_roman(s), n, f"from_roman({s!r})")

    def test_round_trip(self):
        for n in (1, 14, 49, 88, 271, 1666, 2421, 3888):
            self.assertEqual(self.r.from_roman(self.r.to_roman(n)), n)


if __name__ == "__main__":
    unittest.main()
