"""Fixed external oracle for the `palindrome` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestPalindrome(unittest.TestCase):
    def setUp(self):
        try:
            import palindrome
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import src/palindrome.py: {e}")
        self.fn = palindrome.is_palindrome

    def test_empty_and_single(self):
        self.assertTrue(self.fn(""))
        self.assertTrue(self.fn("x"))

    def test_true_cases(self):
        self.assertTrue(self.fn("racecar"))
        self.assertTrue(self.fn("A man, a plan, a canal: Panama"))
        self.assertTrue(self.fn("No 'x' in Nixon"))

    def test_false_cases(self):
        self.assertFalse(self.fn("hello"))
        self.assertFalse(self.fn("palindrome"))


if __name__ == "__main__":
    unittest.main()
