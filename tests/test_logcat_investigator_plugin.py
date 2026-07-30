import json
import tempfile
import unittest
from pathlib import Path

from app.plugins.host_workspace import (
    HostWorkspaceBinding,
    resolve_host_workspace,
)
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
from tests.official_plugin_helpers import load


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "plugins/official/logcat_investigator"
MODULE = load("official_logcat_investigator", "logcat_investigator")
PLUGIN_ID = "susadb.logcat-investigator"


class LogcatInvestigatorPluginTests(unittest.TestCase):
    def manager(self, directory):
        store = PluginStore(Path(directory) / "store")
        return PluginManager(
            store,
            PluginTrustStore(store.root / "state/trust.json"),
            ContributionRegistry(),
            official_root=ROOT / "plugins/official",
        )

    def test_manifest_identity_capabilities_and_inactive_defaults(self):
        manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["plugin_id"], PLUGIN_ID)
        self.assertEqual(manifest["name"], "Logcat Investigator")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["plugin_api_version"], "1.1")
        self.assertEqual(
            manifest["requested_capabilities"],
            ["read-selected-device", "read-device-logs"],
        )
        self.assertFalse(manifest["enabled"])
        contribution = manifest["contributed_components"][0]
        self.assertEqual(contribution["contribution_id"], "logcat-investigator.panel")
        self.assertEqual(contribution["metadata"]["workspace_kind"], "logcat-investigator")
        self.assertTrue(contribution["metadata"]["device_selector"])

    def test_plugin_uses_public_sdk_and_fallback_is_honest(self):
        source = (SOURCE / "plugin.py").read_text(encoding="utf-8")
        self.assertIn("from app.plugins import", source)
        for forbidden in (
            "app.core",
            "app.gui",
            "import subprocess",
            "import socket",
            "import requests",
            "logcat -v",
        ):
            self.assertNotIn(forbidden, source)
        panel = MODULE.panel_spec()
        self.assertFalse(panel.actions)
        self.assertIn("does not display logs", panel.views[0].body)
        plugin = MODULE.Plugin()
        contributions = plugin.activate(object())
        self.assertEqual(len(contributions), 1)
        plugin.deactivate()
        self.assertIsNone(plugin.api)

    def test_install_trust_enable_load_and_unload_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            item = next(
                value for value in manager.official()
                if value.manifest.plugin_id == PLUGIN_ID
            )
            self.assertTrue(manager.install_official(PLUGIN_ID, item.package_digest).ok)
            self.assertFalse(manager.trust.verify(PLUGIN_ID, item.package_digest))
            self.assertFalse(manager.records[PLUGIN_ID][2].enabled)
            self.assertFalse(manager.load(PLUGIN_ID).ok)
            self.assertTrue(
                manager.approve(
                    PLUGIN_ID,
                    ("read-selected-device", "read-device-logs"),
                ).ok
            )
            self.assertFalse(manager.records[PLUGIN_ID][2].enabled)
            self.assertTrue(manager.enable(PLUGIN_ID).ok)
            self.assertFalse(manager.registry.list())
            self.assertTrue(manager.load(PLUGIN_ID).ok)
            self.assertEqual(
                manager.registry.by_plugin(PLUGIN_ID)[0].contribution_id,
                "logcat-investigator.panel",
            )
            self.assertTrue(manager.unload(PLUGIN_ID).ok)
            self.assertFalse(manager.registry.by_plugin(PLUGIN_ID))

    def test_changed_digest_revokes_log_capability_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            item = next(
                value for value in manager.official()
                if value.manifest.plugin_id == PLUGIN_ID
            )
            manager.install_official(PLUGIN_ID, item.package_digest)
            manager.approve(PLUGIN_ID, item.manifest.requested_capabilities)
            installed_path = manager.records[PLUGIN_ID][0]
            (installed_path / "plugin.py").write_text(
                (installed_path / "plugin.py").read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            self.assertFalse(manager.verify(PLUGIN_ID).ok)
            self.assertFalse(manager.trust.verify(PLUGIN_ID, item.package_digest))
            self.assertEqual(manager.trust.approved(PLUGIN_ID, item.package_digest), ())

    def test_host_workspace_requires_both_narrow_capabilities(self):
        binding = HostWorkspaceBinding(
            object(),
            "read-device-logs",
            True,
            ("read-selected-device",),
        )
        values = {"logcat-investigator": binding}
        resolved, error = resolve_host_workspace(
            values,
            workspace_kind="logcat-investigator",
            approved_capabilities=("read-device-logs",),
        )
        self.assertIsNone(resolved)
        self.assertIn("read-selected-device", error)
        resolved, error = resolve_host_workspace(
            values,
            workspace_kind="logcat-investigator",
            approved_capabilities=("read-selected-device", "read-device-logs"),
        )
        self.assertIs(resolved, binding)
        self.assertEqual(error, "")


if __name__ == "__main__":
    unittest.main()
