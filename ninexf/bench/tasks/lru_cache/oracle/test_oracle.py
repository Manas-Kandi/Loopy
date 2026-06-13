"""Fixed external oracle for the `lru_cache` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestLRUCache(unittest.TestCase):
    def setUp(self):
        try:
            from lru_cache import LRUCache
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import LRUCache from src/lru_cache.py: {e}")
        self.LRUCache = LRUCache

    def test_get_absent_is_none(self):
        c = self.LRUCache(2)
        self.assertIsNone(c.get("missing"))

    def test_basic_put_get(self):
        c = self.LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.get("a"), 1)
        self.assertEqual(c.get("b"), 2)

    def test_eviction_of_lru(self):
        c = self.LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)            # capacity 2 -> "a" (least recent) evicted
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)

    def test_get_refreshes_recency(self):
        c = self.LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.get("a"), 1)   # "a" now most-recently used
        c.put("c", 3)                     # "b" should be evicted, not "a"
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("b"))

    def test_update_existing(self):
        c = self.LRUCache(2)
        c.put("a", 1)
        c.put("a", 99)
        self.assertEqual(c.get("a"), 99)


if __name__ == "__main__":
    unittest.main()
