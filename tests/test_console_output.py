import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class ConsoleOutputContractTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "app/gui/console_output.py").read_text(
            encoding="utf-8"
        )
        self.main = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")

    def test_transcript_has_centralized_controlled_api(self):
        for method in (
            "append", "replace", "clear", "read", "copy_selection", "close"
        ):
            self.assertIn(f"def {method}(", self.source)
        self.assertIn('self.configure(state="disabled")', self.source)

    def test_failed_mutation_restores_read_only_state(self):
        mutation = self.source.split("def _mutate", 1)[1].split(
            "def append", 1
        )[0]
        self.assertIn("finally:", mutation)
        self.assertIn('self.configure(state="disabled")', mutation)

    def test_editing_gestures_are_blocked_but_copy_and_select_all_remain(self):
        for sequence in (
            "<Control-c>", "<Control-a>", "<Control-x>", "<Control-v>",
            "<<Cut>>", "<<Paste>>", "<Button-2>",
        ):
            self.assertIn(sequence, self.source)
        self.assertIn('tag_add("sel"', self.source)
        self.assertIn("ClipboardManager.copy(self)", self.source)

    def test_scrolling_and_bindings_are_instance_owned(self):
        self.assertIn("ScopedScrollRouter(", self.source)
        self.assertIn("ScopedEventBindings()", self.source)
        self.assertIn("self.scroll_router.close()", self.source)
        self.assertIn("self.bindings.close()", self.source)
        self.assertNotIn("bind_all(", self.source)

    def test_printable_handoff_excludes_shortcuts_and_never_executes(self):
        handler = self.source.split("def _key_pressed", 1)[1].split(
            "def focus_for_reading", 1
        )[0]
        self.assertIn("character.isprintable()", handler)
        self.assertIn("state & self._SHORTCUT_MODIFIERS", handler)
        self.assertIn("self._handoff(character)", handler)
        self.assertNotIn("execute", handler)

    def test_main_uses_only_the_transcript_interface(self):
        self.assertIn("ConsoleOutput(", self.main)
        self.assertIn("self.console.append(", self.main)
        self.assertIn("self.console.replace(", self.main)
        self.assertIn("self.console.read()", self.main)
        for direct in (
            "self.console.insert(", "self.console.delete(",
            'self.console.configure(state=',
        ):
            self.assertNotIn(direct, self.main)


if __name__ == "__main__":
    unittest.main()
