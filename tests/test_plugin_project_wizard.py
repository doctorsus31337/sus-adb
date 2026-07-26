import ast
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_project import PluginProjectGenerator
from app.plugins.plugin_project_wizard import (
    PluginProjectWizardController,
    capability_rows,
)
from app.plugins.plugin_workbench_output import WorkbenchWriteResult


ROOT = Path(__file__).resolve().parents[1]


def ready_controller(factory=PluginProjectGenerator):
    controller = PluginProjectWizardController(factory)
    draft = controller.draft
    draft.project_name = "Wizard Fixture"
    draft.author = "Example Author"
    draft.description = "An inert synthetic Wizard fixture."
    controller.set_plugin_id("example-author.wizard-fixture")
    draft.folder_name = "wizard fixture project"
    draft.contribution_title = "Wizard Fixture"
    return controller


class PluginProjectWizardControllerTests(unittest.TestCase):
    def test_construction_is_lazy_and_defaults_are_api_11_zero_capability(self):
        calls = []
        controller = PluginProjectWizardController(
            lambda: calls.append(True) or PluginProjectGenerator()
        )
        self.assertEqual(calls, [])
        self.assertEqual(controller.draft.capabilities, ())
        controller = ready_controller(controller.generator_factory)
        self.assertEqual(controller.spec().identity.plugin_api_version, "1.1")
        controller.plan()
        self.assertEqual(calls, [])

    def test_suggestions_are_explicit_editable_and_contribution_lock_is_stable(self):
        controller = PluginProjectWizardController()
        controller.draft.project_name = "Project Name"
        controller.draft.author = "Publisher"
        self.assertEqual(
            controller.apply_plugin_id_suggestion(), "publisher.project-name"
        )
        self.assertEqual(
            controller.draft.contribution_id, "publisher.project-name.main"
        )
        controller.set_plugin_id("publisher.edited")
        self.assertEqual(
            controller.draft.contribution_id, "publisher.edited.main"
        )
        controller.set_contribution_id("publisher.edited.window")
        controller.set_plugin_id("publisher.final")
        self.assertEqual(
            controller.draft.contribution_id, "publisher.edited.window"
        )

    def test_capabilities_are_canonical_deduplicated_and_acknowledged(self):
        rows = capability_rows()
        names = tuple(row["name"] for row in rows)
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("adb.shell", names)
        controller = ready_controller()
        controller.set_capabilities(
            ("read-selected-device", "read-selected-device")
        )
        self.assertEqual(
            controller.draft.capabilities, ("read-selected-device",)
        )
        controller.set_capabilities(("access-network",))
        with self.assertRaisesRegex(ValueError, "acknowledgment"):
            controller.spec()
        controller.draft.high_impact_acknowledged = True
        self.assertEqual(controller.spec().capabilities.requested, ("access-network",))
        controller.set_capabilities(("invented",))
        with self.assertRaisesRegex(ValueError, "Unknown"):
            controller.spec()

    def test_review_is_explicit_and_rerender_preserves_success(self):
        calls = []
        controller = ready_controller(
            lambda: calls.append(True) or PluginProjectGenerator()
        )
        first = controller.plan()
        self.assertFalse(controller.validated)
        self.assertEqual(calls, [])
        validation = controller.validate()
        self.assertTrue(validation.ok, validation.errors)
        self.assertEqual(calls, [True])
        self.assertTrue(controller.validated)
        self.assertEqual(controller.plan(), first)
        self.assertTrue(controller.validated)

    def test_folder_zip_and_brief_are_deterministic_and_production_valid(self):
        controller = ready_controller()
        self.assertFalse(
            controller.export_brief("not-written.md").ok
        )
        validation = controller.validate()
        self.assertTrue(validation.ok, validation.errors)
        with tempfile.TemporaryDirectory(prefix="wizard outputs ") as value:
            parent = Path(value)
            folder_result = controller.create_folder(parent)
            self.assertTrue(folder_result.ok, folder_result.error)
            folder = Path(folder_result.path)
            self.assertEqual(folder.parent, parent.resolve())
            first_zip = parent / "first.zip"
            second_zip = parent / "second.zip"
            first = controller.build_zip(first_zip)
            second = controller.build_zip(second_zip)
            self.assertTrue(first.ok, first.error)
            self.assertTrue(second.ok, second.error)
            self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())
            inspection = PluginPackage.inspect(first_zip)
            self.assertTrue(inspection.ok, inspection.error)
            with zipfile.ZipFile(first_zip) as archive:
                self.assertIn("manifest.json", archive.namelist())
                self.assertFalse(any(name.startswith("/") for name in archive.namelist()))
            brief_path = parent / "DEVELOPER_BRIEF.md"
            brief = controller.export_brief(brief_path)
            self.assertTrue(brief.ok, brief.error)
            text = brief_path.read_text(encoding="utf-8")
            self.assertIn("example-author.wizard-fixture", text)
            self.assertNotIn(str(parent), text)

    def test_failed_zip_build_preserves_destination(self):
        controller = ready_controller()
        self.assertTrue(controller.validate().ok)
        with tempfile.TemporaryDirectory() as value:
            destination = Path(value) / "starter.zip"
            destination.write_bytes(b"preserved")
            with patch(
                "app.plugins.plugin_project_wizard."
                "PluginWorkbenchPackageBuilder.build",
                return_value=WorkbenchWriteResult(False, error="synthetic failure"),
            ):
                result = controller.build_zip(destination, overwrite=True)
            self.assertFalse(result.ok)
            self.assertEqual(destination.read_bytes(), b"preserved")

    def test_generated_source_is_inert_public_and_manifest_matches(self):
        controller = ready_controller()
        plan = controller.plan()
        source = plan.file("plugin.py").text
        tree = ast.parse(source)
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertTrue(
            all(
                module in {"__future__", "dataclasses"}
                or module == "app.plugins"
                or module.startswith("app.plugins.")
                for module in imports
            )
        )
        for forbidden in (
            ".success", "subprocess", "socket", "requests", "Tk(",
            "CTk(", "app.core", "app.gui", "adb ",
        ):
            self.assertNotIn(forbidden, source)
        manifest = json.loads(plan.file("manifest.json").text)
        self.assertFalse(manifest["enabled"])
        self.assertEqual(manifest["trust_state"], "untrusted")
        contribution_id = manifest["contributed_components"][0]["contribution_id"]
        self.assertIn(repr(contribution_id), source)

    def test_host_integrations_are_lazy_singleton_and_static_only(self):
        main_source = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")
        menu_source = (ROOT / "app/gui/menu_bar.py").read_text(encoding="utf-8")
        gui_source = (
            ROOT / "app/gui/plugin_project_wizard.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def open_plugin_project_wizard(self)", main_source)
        self.assertIn("self.plugin_project_wizard_window.focus_window()", main_source)
        self.assertIn("Plugin Project Wizard", menu_source)
        for alias in (
            "create plugin", "create addon", "new module", "new addon",
            "plugin wizard", "addon wizard", "module template",
            "plugin scaffold", "SDK project",
        ):
            self.assertIn(alias, main_source)
        self.assertIn("select_candidate(candidate)", main_source)
        self.assertNotIn(".install(", gui_source)
        self.assertNotIn(".load(", gui_source)
        self.assertNotIn("os.walk", gui_source)
        self.assertNotIn("rglob(", gui_source)


if __name__ == "__main__":
    unittest.main()
