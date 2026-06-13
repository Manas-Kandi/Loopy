"""Fixed external oracle for the `greeting` task. Never shown to the solver."""

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent  # _oracle/ -> project root
ENTRY = PROJECT / "src" / "main.py"


class TestGreeting(unittest.TestCase):
    def test_entry_point_exists(self):
        self.assertTrue(ENTRY.exists(), "src/main.py was never created")

    def test_runs_and_greets(self):
        result = subprocess.run(
            [sys.executable, "src/main.py"],
            cwd=str(PROJECT), capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, f"non-zero exit: {result.stderr}")
        self.assertIn("hello", result.stdout.lower(),
                      f"output did not contain a greeting: {result.stdout!r}")


if __name__ == "__main__":
    unittest.main()
