import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_workbench import (
    FindingSeverity,
    InstalledPluginSnapshot,
    PluginWorkbenchAnalyzer,
    PluginWorkbenchSource,
    WorkbenchStatus,
)


MANIFEST = {
    "plugin_id": "example.workbench",
    "name": "Workbench Fixture",
    "version": "1.0.0",
    "entry_point": "plugin.py:Plugin",
    "plugin_api_version": "1.0",
    "requested_capabilities": [],
    "contributed_components": [{
        "contribution_id": "example.panel",
        "contribution_type": "pentest-panel",
        "title": "Fixture",
        "factory": "panel_spec",
    }],
}
PLUGIN = """\
from app.plugins.plugin_api import PluginResult
from app.plugins.plugin_ui import PluginPanelSpec, PluginView
def panel_spec(_context=None):
    return PluginPanelSpec("Fixture", (PluginView("Overview", "Static"),))
class Plugin:
    def activate(self, api):
        return ()
    def deactivate(self):
        self.api = None
"""


class PluginWorkbenchTests(unittest.TestCase):
    def fixture(self, root, manifest=None, plugin=PLUGIN):
        root = Path(root)
        (root / "manifest.json").write_text(
            json.dumps(MANIFEST if manifest is None else manifest), encoding="utf-8"
        )
        (root / "plugin.py").write_text(plugin, encoding="utf-8")
        return root

    def analyze(self, root, **kwargs):
        return PluginWorkbenchAnalyzer(**kwargs).analyze(
            PluginWorkbenchSource.selected(root)
        )

    def rules(self, snapshot):
        return {item.rule_id for item in snapshot.findings}

    def test_valid_candidate_is_static_and_compatible(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "builtins.__import__", wraps=__import__
        ) as importer:
            snapshot = self.analyze(self.fixture(directory))
        self.assertEqual(snapshot.status, WorkbenchStatus.COMPATIBLE)
        self.assertFalse(any(
            call.args and str(call.args[0]).startswith("sus_adb_plugin_")
            for call in importer.call_args_list
        ))
        self.assertEqual(snapshot.manifest.plugin_id, "example.workbench")

    def test_manifest_entry_factory_and_syntax_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self.analyze(root)
            self.assertIn("MAN001", self.rules(snapshot))
            self.fixture(root, plugin="class Plugin(:\n pass\n")
            snapshot = self.analyze(root)
            self.assertIn("PY001", self.rules(snapshot))
            self.assertEqual(snapshot.status, WorkbenchStatus.BLOCKED)

    def test_nested_invalid_duplicate_and_unknown_manifest_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "wrapper"
            nested.mkdir()
            self.fixture(nested)
            self.assertIn("MAN001", self.rules(self.analyze(root)))
            (root / "manifest.json").write_text('{"plugin_id":"a","plugin_id":"b"}')
            self.assertIn("MAN002", self.rules(self.analyze(root)))
        with tempfile.TemporaryDirectory() as directory:
            manifest = {**MANIFEST, "requested_capabilities": ["unknown"]}
            snapshot = self.analyze(self.fixture(directory, manifest))
            self.assertEqual(snapshot.status, WorkbenchStatus.BLOCKED)

    def test_sdk_policy_and_capability_rules(self):
        dangerous = """\
import subprocess, socket, importlib
from app.core.worker import BackgroundWorker
from app.plugins.plugin_api import Missing, PluginResult
from app.plugins.plugin_ui import PluginPanelSpec, PluginView
def panel_spec(_context=None): return PluginPanelSpec("x", (PluginView("x"),))
class Plugin:
 def activate(self, api):
  api.not_real()
  result = PluginResult(True)
  print(result.success)
  eval("1")
  subprocess.run(["adb", "devices"], shell=True)
  return ()
"""
        with tempfile.TemporaryDirectory() as directory:
            snapshot = self.analyze(self.fixture(directory, plugin=dangerous))
        rules = self.rules(snapshot)
        self.assertTrue({"SDK001", "SDK002", "SDK003", "SDK005"} <= rules)
        self.assertTrue({"POL001", "POL002", "POL003", "POL004"} <= rules)

    def test_local_import_allowed_factory_required_and_capability_reconciled(self):
        plugin = """\
from .helpers import value
from app.plugins.plugin_ui import PluginPanelSpec, PluginView
class Plugin:
 def activate(self, api):
  api.write_state({"x": value})
  return ()
"""
        manifest = {
            **MANIFEST,
            "requested_capabilities": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory, manifest, plugin)
            (root / "helpers.py").write_text("value=1\n")
            snapshot = self.analyze(root)
        self.assertIn("CAP002", self.rules(snapshot))
        self.assertIn("CON003", self.rules(snapshot))
        self.assertNotIn("SDK001", [
            item.rule_id for item in snapshot.findings if item.path == "helpers.py"
        ])

    def test_privacy_findings_redact_values_and_clutter_is_excluded(self):
        token = "ghp_" + "A" * 32
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            (root / ".env").write_text(f"API_KEY='{token}'\nHOME=/home/person\n")
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "x.pyc").write_bytes(b"x")
            snapshot = self.analyze(root)
        rendered = repr(snapshot.findings)
        self.assertNotIn(token, rendered)
        self.assertNotIn("/home/person", rendered)
        self.assertTrue({"SEC000", "SEC002", "SEC004", "SEC005"} <= self.rules(snapshot))
        self.assertTrue(any(file.excluded_reason for file in snapshot.files))

    def make_zip(self, path, entries):
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in entries:
                archive.writestr(name, data)

    def test_malicious_zip_matrix(self):
        cases = {
            "traversal": [("../manifest.json", b"{}")],
            "backslash": [(r"..\\manifest.json", b"{}")],
            "reserved": [("CON.txt", b"x")],
            "duplicate": [("manifest.json", b"{}"), ("manifest.json", b"{}")],
            "collision": [("A.py", b"x"), ("a.py", b"x")],
        }
        with tempfile.TemporaryDirectory() as directory:
            for label, entries in cases.items():
                with self.subTest(label=label):
                    path = Path(directory) / f"{label}.zip"
                    self.make_zip(path, entries)
                    snapshot = self.analyze(path)
                    self.assertIn("PKG001", self.rules(snapshot))
                    self.assertEqual(snapshot.status, WorkbenchStatus.BLOCKED)

    def test_directory_symlink_and_limits_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            (root / "link").symlink_to(root / "plugin.py")
            self.assertIn("PKG001", self.rules(self.analyze(root)))
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            (root / "large.bin").write_bytes(b"x" * 20)
            analyzer = PluginWorkbenchAnalyzer()
            analyzer.MAX_FILE = 10
            self.assertIn("PKG001", self.rules(analyzer.analyze(root)))

    def test_cancel_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                PluginWorkbenchAnalyzer(cancelled=lambda: True).analyze(root)

    def test_installed_comparison_is_static_and_clear(self):
        with tempfile.TemporaryDirectory() as old_dir, tempfile.TemporaryDirectory() as new_dir:
            old = self.fixture(old_dir)
            inspection = PluginPackage.inspect(old)
            installed = InstalledPluginSnapshot.from_inspection(inspection)
            manifest = {**MANIFEST, "requested_capabilities": ["read-selected-device"]}
            new = self.fixture(new_dir, manifest, PLUGIN + "\n# changed\n")
            snapshot = self.analyze(
                new, installed={installed.plugin_id: installed}
            )
        comparison = snapshot.comparison
        self.assertTrue(comparison.same_version_digest_changed)
        self.assertEqual(comparison.capability_additions, ("read-selected-device",))
        self.assertIn("plugin.py", comparison.modified_files)

    def test_no_absolute_source_path_in_snapshot_or_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = self.analyze(self.fixture(directory))
            self.assertNotIn(str(Path(directory).resolve()), repr(snapshot))


if __name__ == "__main__":
    unittest.main()
