"""Guard: every bench oracle must PASS against a known-good reference solution.

A benchmark is only meaningful if its oracles are correct and satisfiable. This
test holds a reference implementation for each task and asserts the oracle passes
against it. Adding a new task without a reference here fails the suite by design —
that forces the author to prove the oracle can actually be solved before it grades
any model."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ninexf.bench.spec import all_task_names, load_task

REFERENCE = {
    "greeting": ("src/main.py",
        "def main():\n    print('hello world')\n\nif __name__ == '__main__':\n    main()\n"),
    "calculator": ("src/calculator.py",
        "def add(a, b): return a + b\n"
        "def subtract(a, b): return a - b\n"
        "def multiply(a, b): return a * b\n"
        "def divide(a, b):\n"
        "    if b == 0: raise ValueError('division by zero')\n"
        "    return a / b\n"),
    "fizzbuzz": ("src/fizzbuzz.py",
        "def fizzbuzz(n):\n"
        "    out = []\n"
        "    for i in range(1, n + 1):\n"
        "        if i % 15 == 0: out.append('FizzBuzz')\n"
        "        elif i % 3 == 0: out.append('Fizz')\n"
        "        elif i % 5 == 0: out.append('Buzz')\n"
        "        else: out.append(str(i))\n"
        "    return out\n"),
    "palindrome": ("src/palindrome.py",
        "def is_palindrome(s):\n"
        "    cleaned = [c.lower() for c in s if c.isalnum()]\n"
        "    return cleaned == cleaned[::-1]\n"),
    "temperature": ("src/temperature.py",
        "def celsius_to_fahrenheit(c): return c * 9 / 5 + 32\n"
        "def fahrenheit_to_celsius(f): return (f - 32) * 5 / 9\n"
        "def celsius_to_kelvin(c): return c + 273.15\n"),
    "word_count": ("src/word_count.py",
        "import re\n"
        "def word_frequencies(text):\n"
        "    counts = {}\n"
        "    for w in re.findall(r'[a-zA-Z0-9]+', text.lower()):\n"
        "        counts[w] = counts.get(w, 0) + 1\n"
        "    return counts\n"),
    "roman": ("src/roman.py",
        "_VALS = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),\n"
        "         (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]\n"
        "def to_roman(n):\n"
        "    out = []\n"
        "    for v, s in _VALS:\n"
        "        while n >= v:\n"
        "            out.append(s); n -= v\n"
        "    return ''.join(out)\n"
        "def from_roman(s):\n"
        "    m = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n"
        "    total = 0; prev = 0\n"
        "    for ch in reversed(s):\n"
        "        v = m[ch]\n"
        "        total += -v if v < prev else v\n"
        "        prev = v\n"
        "    return total\n"),
    "rpn": ("src/rpn.py",
        "def evaluate(expr):\n"
        "    ops = {'+':lambda a,b:a+b,'-':lambda a,b:a-b,'*':lambda a,b:a*b,'/':lambda a,b:a/b}\n"
        "    stack = []\n"
        "    for tok in expr.split():\n"
        "        if tok in ops:\n"
        "            if len(stack) < 2: raise ValueError('too few operands')\n"
        "            b = stack.pop(); a = stack.pop()\n"
        "            stack.append(ops[tok](a, b))\n"
        "        else:\n"
        "            try: stack.append(float(tok))\n"
        "            except ValueError: raise ValueError(f'unknown token {tok!r}')\n"
        "    if len(stack) != 1: raise ValueError('malformed expression')\n"
        "    return stack[0]\n"),
    "linked_list": ("src/linked_list.py",
        "class _Node:\n"
        "    def __init__(self, value):\n"
        "        self.value = value; self.next = None\n"
        "class LinkedList:\n"
        "    def __init__(self): self.head = None\n"
        "    def append(self, value):\n"
        "        node = _Node(value)\n"
        "        if not self.head: self.head = node; return\n"
        "        cur = self.head\n"
        "        while cur.next: cur = cur.next\n"
        "        cur.next = node\n"
        "    def to_list(self):\n"
        "        out = []; cur = self.head\n"
        "        while cur: out.append(cur.value); cur = cur.next\n"
        "        return out\n"
        "    def reverse(self):\n"
        "        prev = None; cur = self.head\n"
        "        while cur:\n"
        "            nxt = cur.next; cur.next = prev; prev = cur; cur = nxt\n"
        "        self.head = prev\n"),
    "flatten": ("src/flatten.py",
        "def flatten(d, sep='.'):\n"
        "    out = {}\n"
        "    def go(cur, prefix):\n"
        "        for k, v in cur.items():\n"
        "            key = f'{prefix}{sep}{k}' if prefix else str(k)\n"
        "            if isinstance(v, dict): go(v, key)\n"
        "            else: out[key] = v\n"
        "    go(d, '')\n"
        "    return out\n"),
    "lru_cache": ("src/lru_cache.py",
        "from collections import OrderedDict\n"
        "class LRUCache:\n"
        "    def __init__(self, capacity):\n"
        "        self.capacity = capacity; self.data = OrderedDict()\n"
        "    def get(self, key):\n"
        "        if key not in self.data: return None\n"
        "        self.data.move_to_end(key)\n"
        "        return self.data[key]\n"
        "    def put(self, key, value):\n"
        "        if key in self.data: self.data.move_to_end(key)\n"
        "        self.data[key] = value\n"
        "        if len(self.data) > self.capacity: self.data.popitem(last=False)\n"),
    "anagram_groups": ("src/anagram_groups.py",
        "def group_anagrams(words):\n"
        "    groups = {}\n"
        "    for w in words:\n"
        "        groups.setdefault(''.join(sorted(w)), []).append(w)\n"
        "    return list(groups.values())\n"),
}


def _run_oracle_against_reference(name: str) -> subprocess.CompletedProcess:
    task = load_task(name)
    rel, body = REFERENCE[name]
    proj = Path(tempfile.mkdtemp(prefix=f"9xf-oracle-{name}-"))
    try:
        (proj / "src").mkdir()
        (proj / rel).write_text(body)
        suite = proj / "_oracle"
        suite.mkdir()
        (suite / "__init__.py").touch()
        for f in task.oracle_dir.glob("test_*.py"):
            shutil.copy(f, suite / f.name)
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "_oracle", "-t", "."],
            cwd=proj, capture_output=True, text=True,
        )
    finally:
        shutil.rmtree(proj, ignore_errors=True)


class TestOracleValidity(unittest.TestCase):
    def test_every_task_has_a_reference(self):
        missing = [n for n in all_task_names() if n not in REFERENCE]
        self.assertEqual(missing, [], f"tasks without a reference solution: {missing}")

    def test_oracles_pass_against_reference(self):
        for name in all_task_names():
            with self.subTest(task=name):
                self.assertIn(name, REFERENCE, f"no reference solution for {name}")
                r = _run_oracle_against_reference(name)
                self.assertEqual(r.returncode, 0,
                                 f"oracle for {name} failed against a correct "
                                 f"solution:\n{r.stdout[-1500:]}\n{r.stderr[-800:]}")


if __name__ == "__main__":
    unittest.main()
