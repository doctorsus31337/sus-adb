import unittest
from pathlib import Path

from app.core.command_completion import CommandCompletionService
from app.core.history_manager import HistoryManager


ROOT = Path(__file__).parents[1]


class CommandBarContractTests(unittest.TestCase):
    def test_suggestion_acceptance_is_text_only(self):
        result = CommandCompletionService().suggest("adb reboot b")
        suggestion = result.suggestions[0]
        value, cursor = suggestion.apply("adb reboot b")
        self.assertEqual(value, "adb reboot bootloader")
        self.assertEqual(cursor, len(value))
        self.assertFalse(any("callback" in slot for slot in suggestion.__slots__))

    def test_history_navigation_is_non_executing_and_deduplicated(self):
        history = HistoryManager()
        for value in ("adb devices -l", "adb devices -l", "help"):
            history.add(value)
        self.assertEqual(history.entries(), ("adb devices -l", "help"))
        self.assertEqual(history.previous(), "help")
        self.assertEqual(history.previous(), "adb devices -l")
        self.assertEqual(history.next(), "help")
        history.reset_navigation()
        self.assertEqual(history.previous(), "help")

    def test_assistant_has_no_execution_backend_or_global_binding(self):
        source = (ROOT / "app/gui/command_bar.py").read_text(encoding="utf-8")
        for forbidden in (
            "subprocess", "ADBManager", "FridaManager", "ObjectionManager",
            "BackgroundWorker", "bind_all(", "Path.home", "os.listdir",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("ScopedEventBindings", source)
        self.assertIn("ScopedScrollRouter", source)
        self.assertIn("self.execute_callback(command)", source)
        self.assertLess(
            source.index("self.hide_suggestions()", source.index("def run(")),
            source.index("self.execute_callback(command)", source.index("def run(")),
        )

    def test_keyboard_contract_is_instance_scoped(self):
        source = (ROOT / "app/gui/command_bar.py").read_text(encoding="utf-8")
        for sequence in (
            '"<Return>"', '"<Tab>"', '"<ISO_Left_Tab>"', '"<Up>"', '"<Down>"',
            '"<Prior>"', '"<Next>"', '"<Escape>"', '"<Control-space>"', '"<Right>"',
            '"<Control-a>"', '"<Control-A>"', '"<Command-a>"', '"<Command-A>"',
        ):
            self.assertIn(sequence, source)
        self.assertIn("self.bindings.close()", source)
        self.assertIn("self._cancel_refresh()", source)

    def test_select_all_is_scoped_text_selection_only(self):
        source = (ROOT / "app/gui/command_bar.py").read_text(encoding="utf-8")
        selector = source.split("def _select_all_command", 1)[1].split(
            "def _key_released", 1
        )[0]
        self.assertIn('getattr(self.entry, "_entry", self.entry)', selector)
        self.assertIn('target.selection_range(0, "end")', selector)
        self.assertIn('target.icursor("end")', selector)
        self.assertIn('return "break"', selector)
        self.assertNotIn("execute_callback", selector)
        self.assertNotIn("history.add", selector)
        self.assertNotIn("accept_index", selector)

    def test_command_modifier_is_macos_only(self):
        source = (ROOT / "app/gui/command_bar.py").read_text(encoding="utf-8")
        sequences = source.split("def _select_all_sequences", 1)[1].split(
            "def _select_all_command", 1
        )[0]
        self.assertIn('== "darwin"', sequences)
        self.assertIn('("<Command-a>", "<Command-A>")', sequences)

    def test_main_reuses_terminal_history_router_and_sanitized_snapshot(self):
        source = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")
        self.assertIn("history=self.terminal.history", source)
        self.assertIn("self.host_state.snapshot()", source)
        self.assertIn("self.host_tools.cached(name)", source)
        self.assertIn('"adb", "fastboot", "frida"', source)
        self.assertIn("self.terminal.execute(command)", source)
        self.assertIn("self.command_bar.close()", source)
        context = source.split("def _command_completion_context", 1)[1].split(
            "def _interactive_command_requested", 1
        )[0]
        for forbidden in ("resolve(", "refresh_devices(", "subprocess", "manager"):
            self.assertNotIn(forbidden, context)

    def test_transcript_handoff_is_text_only_and_non_executing(self):
        source = (ROOT / "app/gui/command_bar.py").read_text(encoding="utf-8")
        handoff = source.split("def handoff_character", 1)[1].split(
            "def _tab", 1
        )[0]
        self.assertIn("self.entry.insert(cursor, character)", handoff)
        self.assertIn("self._schedule_refresh()", handoff)
        self.assertNotIn("execute_callback", handoff)
        self.assertNotIn(".run(", handoff)

    def test_cheat_sheet_uses_advanced_canonical_registry(self):
        source = (ROOT / "app/gui/cheat_sheet_window.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("CommandRegistry.render_text(advanced=True)", source)

    def test_fastboot_serial_has_a_distinct_assistant_badge(self):
        source = (ROOT / "app/gui/command_bar.py").read_text(encoding="utf-8")
        self.assertIn(
            '"Fastboot serial" if suggestion.requires_fastboot_serial else ""',
            source,
        )


if __name__ == "__main__":
    unittest.main()
