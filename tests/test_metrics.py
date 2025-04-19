import unittest

import aisexporter.metrics


class TestMetrics(unittest.TestCase):
    """Check metrics spec structure"""

    def test_specification(self):
        """check structure of specification"""
        self.assertIsInstance(aisexporter.metrics.Specs, dict)

        self.assertIn("ships", aisexporter.metrics.Specs)
        v = aisexporter.metrics.Specs["ships"]
        self.assertIsInstance(v, tuple)
        for i in v:
            self.assertIsInstance(i, tuple)
            self.assertEqual(len(i), 3)

        self.assertIn("stats", aisexporter.metrics.Specs)
        v = aisexporter.metrics.Specs["stats"]
        self.assertIsInstance(v, dict)
        for k1, v1 in v.items():
            self.assertIsInstance(k1, str)
            for i in v1:
                self.assertIsInstance(i, tuple)
                self.assertEqual(len(i), 3)
