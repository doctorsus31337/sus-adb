"""Copy-safe starting test; uses no device, process, network, or GUI."""
import unittest

class SkeletonLifecycleTest(unittest.TestCase):
    def test_template_starts_inert(self):
        self.assertTrue(True)
