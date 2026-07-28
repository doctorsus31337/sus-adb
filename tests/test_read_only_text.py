import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class ReadOnlyTextAuditContractTests(unittest.TestCase):
    def setUp(self):
        self.component = (ROOT / "app/gui/read_only_text.py").read_text(
            encoding="utf-8"
        )

    def test_component_owns_complete_controlled_api(self):
        for method in (
            "append", "replace", "clear", "read", "insert", "delete",
            "copy_selection", "select_all", "focus_for_reading", "close",
        ):
            self.assertIn(f"def {method}(", self.component)
        self.assertIn("finally:", self.component)
        self.assertIn('super().configure(state="disabled")', self.component)

    def test_editing_is_blocked_without_global_bindings(self):
        for sequence in (
            "<KeyPress>", "<Control-c>", "<Control-C>",
            "<Control-a>", "<Control-A>", "<Control-x>", "<Control-X>",
            "<Control-v>", "<Control-V>", "<<Cut>>", "<<Paste>>",
            "<Button-2>",
        ):
            self.assertIn(sequence, self.component)
        self.assertNotIn("bind_all(", self.component)
        self.assertIn("ScopedEventBindings()", self.component)
        self.assertIn("ScopedScrollRouter(", self.component)

    def test_script_studio_classification_is_explicit(self):
        source = (ROOT / "app/gui/script_studio_panel.py").read_text(
            encoding="utf-8"
        )
        for name in (
            "library_details", "operation_details", "rpc_result",
            "message_view", "profile_view",
        ):
            declaration = source.split(f"self.{name} =", 1)[1].split(
                "\n", 1
            )[0]
            self.assertIn("ReadOnlyTextView", declaration)
        editor = source.split("self.editor =", 1)[1].split("\n", 1)[0]
        self.assertIn("ctk.CTkTextbox", editor)
        for name in ("post_entry", "rpc_export", "rpc_args"):
            declaration = source.split(f"self.{name} =", 1)[1].split(
                "\n", 1
            )[0]
            self.assertIn("self._entry", declaration)

    def test_only_intentional_editable_multiline_widgets_remain(self):
        expected = {
            "findings_reporting_panel.py",
            "pentest_workspace.py",
            "plugin_manager_panel.py",
            "script_studio_panel.py",
            "read_only_text.py",
            "customtkinter_compat.py",
        }
        found = {
            path.name
            for path in (ROOT / "app/gui").glob("*.py")
            if "CTkTextbox" in path.read_text(encoding="utf-8")
        }
        self.assertEqual(found, expected)

    def test_display_owners_use_the_canonical_component(self):
        owners = (
            "adb_explorer_panel.py", "addons_center.py",
            "apk_laboratory_panel.py", "cheat_sheet_window.py",
            "context_help_window.py", "contextual_assistant_panel.py",
            "crash_dialog.py", "device_recovery_panel.py",
            "environment_diagnostics_window.py", "first_run_dialog.py",
            "guided_setup_window.py", "instrumentation_panel.py",
            "instrumentation_readiness_panel.py", "learning_center_window.py",
            "network_workspace_panel.py", "plugin_project_wizard.py",
            "plugin_workbench_window.py", "runtime_explorer_panel.py",
            "sessions_center.py", "storage_workspace_panel.py",
        )
        for name in owners:
            with self.subTest(name=name):
                source = (ROOT / "app/gui" / name).read_text(encoding="utf-8")
                self.assertIn("ReadOnlyTextView", source)


if __name__ == "__main__":
    unittest.main()
