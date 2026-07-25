import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from app.core.workspace_navigation import (
    PRINCIPAL_WORKSPACES,
    PrincipalWorkspaceController,
    WorkspaceHomeState,
    abbreviated_serial,
    normalize_workspace,
)


ROOT = Path(__file__).parents[1]


class WorkspaceNavigationTests(unittest.TestCase):
    def test_known_aliases_and_invalid_values_fall_back_to_home(self):
        self.assertEqual(normalize_workspace("Script Studio"), "Scripts")
        self.assertEqual(normalize_workspace("workspace home"), "Home")
        for value in (None, "", "Unknown", object()):
            self.assertEqual(normalize_workspace(value), "Home")

    def test_controller_routes_every_entry_point_through_one_callback(self):
        shown = []
        controller = PrincipalWorkspaceController(
            lambda name: shown.append(name) or name,
            initial="not-a-workspace",
        )
        self.assertEqual(controller.current, "Home")
        self.assertEqual(controller.navigate("Script Studio"), "Scripts")
        self.assertEqual(controller.current, "Scripts")
        self.assertEqual(controller.navigate("invalid"), "Home")
        self.assertEqual(shown, ["Scripts", "Home"])
        self.assertEqual(
            PRINCIPAL_WORKSPACES,
            ("Home", "Console", "Instrumentation", "Scripts", "Pentest"),
        )

    def test_home_state_is_small_and_immutable(self):
        state = WorkspaceHomeState(selected_serial="SERIAL", active_sessions=2)
        with self.assertRaises(FrozenInstanceError):
            state.selected_serial = "OTHER"
        self.assertEqual(state.selected_serial, "SERIAL")

    def test_home_and_dock_do_not_own_device_or_tool_managers(self):
        home = (ROOT / "app/gui/workspace_home.py").read_text(encoding="utf-8")
        dock = (ROOT / "app/gui/device_dock.py").read_text(encoding="utf-8")
        for source in (home, dock):
            self.assertNotIn("DeviceManager", source)
            self.assertNotIn("ADBManager", source)
            self.assertNotIn("FridaManager", source)
            self.assertNotIn("PluginManager", source)
            self.assertNotIn("BackgroundWorker", source)
        self.assertNotIn("refresh_devices(", home)
        self.assertNotIn("scan(", home)
        self.assertIn("self.after(750, self.ensure_content)", home)
        self.assertIn("self.after_cancel(self._content_after_id)", home)

    def test_home_is_progressive_and_secondary_tools_remain_subordinate(self):
        home = (ROOT / "app/gui/workspace_home.py").read_text(encoding="utf-8")
        main = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")
        self.assertIn("self.open_button = self", home)
        self.assertIn("OPEN →", home)
        for title in (
            "Console", "Instrumentation", "Device Recovery",
            "Script Studio", "Pentest", "Sessions",
        ):
            self.assertIn(f'"{title}"', home)
        for title in (
            "Add-ons Center", "Learning Center", "Environment Diagnostics",
            "Contextual Help", "Advanced Command Reference",
        ):
            self.assertIn(f'"{title}"', main)
        self.assertIn('fg_color=theme["panel_alt"]', home)

    def test_serial_abbreviation_preserves_short_and_distinguishes_long(self):
        self.assertEqual(abbreviated_serial("ABC123"), "ABC123")
        value = abbreviated_serial("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.assertEqual(value, "01234567…UVWXYZ")


if __name__ == "__main__":
    unittest.main()
