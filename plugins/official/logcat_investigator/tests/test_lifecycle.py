"""Static package lifecycle contract; no ADB, device, process, network, or GUI."""

import json
import unittest
from pathlib import Path


class LogcatInvestigatorLifecycleTest(unittest.TestCase):
    def test_package_starts_inert(self):
        manifest = json.loads(
            (Path(__file__).parents[1] / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["version"], "0.2.0")
        self.assertFalse(manifest["enabled"])
        self.assertEqual(
            manifest["requested_capabilities"],
            ["read-selected-device", "read-device-logs"],
        )
