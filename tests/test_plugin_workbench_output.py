import ast
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock

from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_workbench import (
    PluginWorkbenchAnalyzer,
    PluginWorkbenchSource,
)
from app.plugins.plugin_workbench_output import (
    PluginWorkbenchPackageBuilder,
    atomic_write_report,
    render_json_report,
    render_markdown_report,
)


MANIFEST = {
    "plugin_id": "example.output",
    "name": "Output Fixture",
    "version": "1.2.3",
    "entry_point": "plugin.py:Plugin",
    "plugin_api_version": "1.0",
    "requested_capabilities": [],
    "contributed_components": [],
}
PLUGIN = """\
class Plugin:
    def activate(self, api):
        return ()
    def deactivate(self):
        self.api = None
"""


class PluginWorkbenchOutputTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root)
        (root / "manifest.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
        (root / "plugin.py").write_text(PLUGIN, encoding="utf-8")
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        clutter = root / "__pycache__"
        clutter.mkdir()
        (clutter / "fixture.pyc").write_bytes(b"not bytecode")
        source = PluginWorkbenchSource.selected(root)
        snapshot = PluginWorkbenchAnalyzer().analyze(source)
        return source, snapshot

    def test_reports_are_deterministic_relative_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            source, snapshot = self.fixture(directory)
            first_json = render_json_report(snapshot)
            second_json = render_json_report(snapshot)
            first_markdown = render_markdown_report(snapshot)
        self.assertEqual(first_json, second_json)
        self.assertNotIn(str(source.path), first_json)
        self.assertNotIn(str(source.path), first_markdown)
        self.assertIn("does not prove third-party code is safe", first_json)
        self.assertEqual(json.loads(first_json)["candidate"]["status"], "Needs Review")

    def test_atomic_report_requires_overwrite_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "report.json"
            destination.write_text("old", encoding="utf-8")
            result = atomic_write_report(destination, "new")
            self.assertFalse(result.ok)
            self.assertEqual(destination.read_text(), "old")
            self.assertTrue(atomic_write_report(destination, "new", overwrite=True).ok)
            self.assertEqual(destination.read_text(), "new")

    def test_plan_excludes_clutter_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source, snapshot = self.fixture(directory)
            plan = PluginWorkbenchPackageBuilder().plan(source, snapshot)
            self.assertTrue(plan.allowed)
            self.assertIn("manifest.json", plan.included)
            self.assertTrue(any("__pycache__" in path for path, _ in plan.excluded))
            self.assertTrue((source.path / "__pycache__/fixture.pyc").exists())

    def test_package_is_deterministic_rooted_and_production_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            source, snapshot = self.fixture(root)
            builder = PluginWorkbenchPackageBuilder()
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            one = builder.build(source, snapshot, first)
            two = builder.build(source, snapshot, second)
            self.assertTrue(one.ok, one.error)
            self.assertTrue(two.ok, two.error)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(one.digest, two.digest)
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["README.md", "manifest.json", "plugin.py"],
                )
                self.assertNotIn("__pycache__/fixture.pyc", archive.namelist())
            self.assertTrue(PluginPackage.inspect(first).ok)

    def test_build_does_not_install_and_requires_overwrite(self):
        install = Mock()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            source, snapshot = self.fixture(root)
            destination = Path(directory) / "plugin.zip"
            destination.write_bytes(b"old")
            builder = PluginWorkbenchPackageBuilder()
            result = builder.build(source, snapshot, destination)
            self.assertFalse(result.ok)
            self.assertEqual(destination.read_bytes(), b"old")
            self.assertTrue(
                builder.build(source, snapshot, destination, overwrite=True).ok
            )
        install.assert_not_called()

    def test_blocked_secret_candidate_cannot_build(self):
        with tempfile.TemporaryDirectory() as directory:
            source, _snapshot = self.fixture(directory)
            (source.path / ".env").write_text("API_KEY='definitely-secret'\n")
            snapshot = PluginWorkbenchAnalyzer().analyze(source)
            plan = PluginWorkbenchPackageBuilder().plan(source, snapshot)
            self.assertFalse(plan.allowed)
            self.assertIn("secret", plan.reason)

    def test_zip_candidate_cannot_be_repackaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            source, snapshot = self.fixture(root)
            archive = Path(directory) / "source.zip"
            self.assertTrue(
                PluginWorkbenchPackageBuilder().build(source, snapshot, archive).ok
            )
            zip_source = PluginWorkbenchSource.selected(archive)
            zip_snapshot = PluginWorkbenchAnalyzer().analyze(zip_source)
            self.assertFalse(
                PluginWorkbenchPackageBuilder().plan(zip_source, zip_snapshot).allowed
            )


class PluginWorkbenchIntegrationSourceTests(unittest.TestCase):
    def test_host_integration_is_lazy_and_reuses_manager_install(self):
        source = Path("app/gui/main_window.py").read_text(encoding="utf-8")
        initialization = source[source.index("self.plugin_workbench_window=None"):]
        self.assertIn("def open_plugin_workbench", source)
        self.assertIn("install_callback=self.plugin_manager.install", source)
        self.assertNotIn("PluginWorkbenchWindow(", initialization.split(
            "def open_plugin_workbench", 1
        )[0])

    def test_tools_and_palette_use_same_opener(self):
        menu = Path("app/gui/menu_bar.py").read_text(encoding="utf-8")
        host = Path("app/gui/main_window.py").read_text(encoding="utf-8")
        self.assertIn(
            'label="Plugin Developer Workbench", command=window.open_plugin_workbench',
            menu,
        )
        self.assertIn("lambda _query:self.open_plugin_workbench()", host)

    def test_workbench_has_no_execution_or_manager_imports(self):
        gui = Path("app/gui/plugin_workbench_window.py").read_text(encoding="utf-8")
        core = Path("app/plugins/plugin_workbench.py").read_text(encoding="utf-8")
        for forbidden in (
            "importlib", "subprocess", "eval(", "exec(", "PluginLoader",
            "PluginManager", "PluginTrustStore",
        ):
            self.assertNotIn(forbidden, gui)
        imported = {
            alias.name
            for node in ast.walk(ast.parse(core))
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module
            for node in ast.walk(ast.parse(core))
            if isinstance(node, ast.ImportFrom)
        }
        self.assertNotIn("importlib", imported)
        self.assertNotIn("subprocess", imported)


if __name__ == "__main__":
    unittest.main()
