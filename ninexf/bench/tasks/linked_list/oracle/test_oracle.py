"""Fixed external oracle for the `linked_list` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestLinkedList(unittest.TestCase):
    def setUp(self):
        try:
            from linked_list import LinkedList
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import LinkedList from src/linked_list.py: {e}")
        self.LinkedList = LinkedList

    def test_empty(self):
        self.assertEqual(self.LinkedList().to_list(), [])

    def test_append_and_to_list(self):
        ll = self.LinkedList()
        for v in (1, 2, 3):
            ll.append(v)
        self.assertEqual(ll.to_list(), [1, 2, 3])

    def test_reverse(self):
        ll = self.LinkedList()
        for v in (1, 2, 3, 4):
            ll.append(v)
        ll.reverse()
        self.assertEqual(ll.to_list(), [4, 3, 2, 1])

    def test_reverse_single(self):
        ll = self.LinkedList()
        ll.append(42)
        ll.reverse()
        self.assertEqual(ll.to_list(), [42])


if __name__ == "__main__":
    unittest.main()
