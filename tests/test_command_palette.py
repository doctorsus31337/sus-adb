import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from app.core.command_palette import (
    CommandPaletteRegistry,
    PaletteCommand,
)


ROOT = Path(__file__).parents[1]


def command(command_id, title, aliases=(), description="", category="Tools"):
    return PaletteCommand(
        command_id,
        title,
        description or f"Open {title}",
        category,
        tuple(aliases),
        invoke=lambda query: (command_id, query),
    )


class CommandPaletteModelTests(unittest.TestCase):
    def setUp(self):
        self.registry = CommandPaletteRegistry(
            (
                command("sessions", "Sessions Center", ("adb shell", "sessions")),
                command("frida", "Frida Assistant", ("frida",)),
                command(
                    "instrumentation", "Instrumentation", ("frida targets",),
                    category="Workspaces",
                ),
                command("objection", "Objection Assistant", ("objection",)),
                command("recovery", "Device Rescue & Recovery", ("recovery",)),
                command("console", "Console", ("terminal",), category="Workspaces"),
            )
        )

    def ids(self, query, limit=16):
        return tuple(
            match.command.command_id
            for match in self.registry.search(query, limit)
        )

    def test_specification_is_immutable_and_widget_free(self):
        value = command("home", "Workspace Home")
        with self.assertRaises(FrozenInstanceError):
            value.title = "Changed"
        self.assertFalse(any("widget" in name for name in value.__slots__))

    def test_exact_title_and_alias_rank_first(self):
        self.assertEqual(self.ids("Console")[0], "console")
        self.assertEqual(self.ids("adb shell")[0], "sessions")

    def test_title_and_word_prefix_ranking(self):
        self.assertEqual(self.ids("sess")[0], "sessions")
        self.assertEqual(self.ids("rescue")[0], "recovery")

    def test_substring_and_ordered_fuzzy_ranking(self):
        self.assertEqual(self.ids("strument")[0], "instrumentation")
        self.assertEqual(self.ids("frda")[0], "frida")

    def test_related_aliases_return_expected_safe_destinations(self):
        self.assertIn("frida", self.ids("frida"))
        self.assertIn("instrumentation", self.ids("frida"))
        self.assertEqual(self.ids("objection")[0], "objection")
        self.assertEqual(self.ids("recovery")[0], "recovery")

    def test_stable_tie_ordering(self):
        first = self.ids("open")
        for _ in range(5):
            self.assertEqual(self.ids("open"), first)

    def test_result_limit_is_enforced(self):
        values = tuple(command(f"c{index:02}", f"Command {index:02}") for index in range(40))
        registry = CommandPaletteRegistry(values)
        self.assertEqual(len(registry.search("command", 12)), 12)

    def test_empty_query_shows_recent_then_common(self):
        registry = CommandPaletteRegistry(
            (
                PaletteCommand(
                    "home", "Workspace Home", "Open", "Workspaces",
                    default_rank=0, invoke=lambda _query: None,
                ),
                PaletteCommand(
                    "sessions", "Sessions Center", "Open", "Tools",
                    default_rank=5, invoke=lambda _query: None,
                ),
            )
        )
        self.assertEqual(registry.search()[0].command.command_id, "home")
        registry.invoke("sessions")
        self.assertEqual(registry.search()[0].command.command_id, "sessions")

    def test_unavailable_result_never_invokes(self):
        called = []
        registry = CommandPaletteRegistry(
            (
                PaletteCommand(
                    "blocked", "Blocked", "Unavailable", "Tools",
                    available=False, unavailable_reason="Missing optional tool",
                    invoke=lambda _query: called.append(True),
                ),
            )
        )
        self.assertIsNone(registry.invoke("blocked", "query"))
        self.assertFalse(called)
        self.assertFalse(registry.recent_ids)

    def test_invocation_receives_query_and_recents_are_bounded(self):
        received = []
        registry = CommandPaletteRegistry(
            tuple(
                PaletteCommand(
                    str(index), str(index), "", "Tools",
                    invoke=lambda query, value=index: received.append((value, query)),
                )
                for index in range(4)
            ),
            recent_limit=2,
        )
        for command_id in ("0", "1", "2"):
            registry.invoke(command_id, "help query")
        self.assertEqual(received[-1], (2, "help query"))
        self.assertEqual(registry.recent_ids, ("2", "1"))

    def test_replacement_rejects_duplicate_ids_and_preserves_valid_recents(self):
        self.registry.invoke("sessions")
        with self.assertRaises(ValueError):
            self.registry.replace(
                (command("same", "One"), command("same", "Two"))
            )
        self.registry.replace((command("sessions", "Sessions Center"),))
        self.assertEqual(self.registry.recent_ids, ("sessions",))


class CommandPaletteIntegrationSourceTests(unittest.TestCase):
    def test_palette_is_lazy_and_uses_existing_host_routes(self):
        source = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")
        constructor = source.split("def _initialize_core_services", 1)[1].split(
            "def _build_device_recovery_workspace", 1
        )[0]
        self.assertIn("self.command_palette=None", constructor)
        self.assertIn("self.command_palette_registry=None", constructor)
        self.assertNotIn("CommandPaletteWindow(", constructor)
        self.assertIn("self.workspace_controller.navigate(name)", source)
        self.assertIn("self.addon_window_host.open(contribution_id)", source)

    def test_view_menu_and_control_k_use_one_host_opener(self):
        menu = (ROOT / "app/gui/menu_bar.py").read_text(encoding="utf-8")
        main = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")
        self.assertIn('label="Command Palette"', menu)
        self.assertIn('accelerator="Ctrl+K"', menu)
        self.assertIn("command=window.open_command_palette", menu)
        self.assertIn("self._install_command_palette_shortcut()", main)
        self.assertIn("self._remove_command_palette_shortcut()", main)

    def test_palette_does_not_import_managers_or_execute_commands(self):
        source = (ROOT / "app/gui/command_palette.py").read_text(encoding="utf-8")
        for value in (
            "DeviceManager", "PluginManager", "ADBManager", "FridaManager",
            "ObjectionManager", "subprocess", "BackgroundWorker",
        ):
            self.assertNotIn(value, source)
        self.assertNotIn("bind_all(", source)
        self.assertIn("result_area.close()", source)


if __name__ == "__main__":
    unittest.main()
