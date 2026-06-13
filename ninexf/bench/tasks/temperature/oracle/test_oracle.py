"""Fixed external oracle for the `temperature` task. Never shown to the solver."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestTemperature(unittest.TestCase):
    def setUp(self):
        try:
            import temperature
        except Exception as e:  # noqa: BLE001
            self.fail(f"could not import src/temperature.py: {e}")
        self.t = temperature

    def test_celsius_to_fahrenheit(self):
        self.assertAlmostEqual(self.t.celsius_to_fahrenheit(0), 32.0)
        self.assertAlmostEqual(self.t.celsius_to_fahrenheit(100), 212.0)
        self.assertAlmostEqual(self.t.celsius_to_fahrenheit(-40), -40.0)

    def test_fahrenheit_to_celsius(self):
        self.assertAlmostEqual(self.t.fahrenheit_to_celsius(32), 0.0)
        self.assertAlmostEqual(self.t.fahrenheit_to_celsius(212), 100.0)

    def test_celsius_to_kelvin(self):
        self.assertAlmostEqual(self.t.celsius_to_kelvin(0), 273.15)
        self.assertAlmostEqual(self.t.celsius_to_kelvin(-273.15), 0.0)


if __name__ == "__main__":
    unittest.main()
