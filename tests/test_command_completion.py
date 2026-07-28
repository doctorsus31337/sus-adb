import unittest
from dataclasses import FrozenInstanceError

from app.core.command_completion import (
    CommandCompletionContext,
    CommandCompletionService,
    CompletionMode,
    parse_partial_command,
)
from app.core.command_registry import CommandSpec


class CommandCompletionTests(unittest.TestCase):
    def setUp(self):
        self.service = CommandCompletionService(visible_limit=10)

    def commands(self, query, context=None, **kwargs):
        return tuple(
            suggestion.command_text
            for suggestion in self.service.suggest(query, context, **kwargs).suggestions
        )

    def test_models_are_immutable_and_gui_neutral(self):
        result = self.service.suggest("adb")
        with self.assertRaises(FrozenInstanceError):
            result.mode = CompletionMode.HIDDEN
        self.assertFalse(
            any("widget" in slot for slot in result.suggestions[0].__slots__)
        )

    def test_a_and_adb_prioritize_adb_commands(self):
        for query in ("a", "adb"):
            with self.subTest(query=query):
                commands = self.commands(query)
                self.assertTrue(commands)
                self.assertTrue(all(value.startswith("adb") for value in commands))

    def test_token_prefix_reboot_and_reconnect(self):
        commands = self.commands("adb r")
        self.assertTrue(commands[0].startswith("adb re"))
        self.assertIn("adb reboot", commands)
        self.assertIn("adb reconnect", commands)

    def test_nested_token_prefix_returns_bootloader(self):
        commands = self.commands("adb reboot b")
        self.assertEqual(commands[0], "adb reboot bootloader")

    def test_exact_start_server_returns_labeled_relationships(self):
        result = self.service.suggest("adb start-server")
        self.assertEqual(result.mode, CompletionMode.RELATED)
        self.assertEqual(
            tuple(item.command_text for item in result.suggestions),
            ("adb devices -l", "adb reconnect", "adb kill-server"),
        )
        self.assertTrue(all(item.related for item in result.suggestions))
        self.assertTrue(all(item.reason == "Related command" for item in result.suggestions))

    def test_editing_exact_command_exits_related_mode(self):
        self.assertEqual(
            self.service.suggest("adb start-server").mode, CompletionMode.RELATED
        )
        self.assertEqual(
            self.service.suggest("adb start-serve").mode, CompletionMode.PREFIX
        )

    def test_token_prefix_outranks_alias(self):
        values = (
            CommandSpec(
                "adb reconnect", "Reconnect", "direct", "ADB", "Server"
            ),
            CommandSpec(
                "tool other", "Other", "alias", "Other", "Reference",
                aliases=("adb re",),
            ),
        )
        service = CommandCompletionService(specs=values)
        result = service.suggest("adb re")
        self.assertEqual(result.suggestions[0].command_id, "direct")
        self.assertEqual(result.suggestions[-1].command_id, "alias")

    def test_full_command_prefix_outranks_alias_description_search_is_not_used(self):
        result = self.service.suggest("adb st")
        self.assertEqual(result.suggestions[0].command_text, "adb start-server")
        self.assertFalse(any("st" in item.description.casefold() and not item.command_text.startswith("adb st") for item in result.suggestions))

    def test_ranking_is_deterministic(self):
        first = self.service.suggest("adb").suggestions
        for _ in range(10):
            self.assertEqual(self.service.suggest("adb").suggestions, first)

    def test_visible_count_is_bounded_and_total_is_separate(self):
        specs = tuple(
            CommandSpec(
                f"adb fixture-{index:02}", "Fixture", f"id-{index:02}", "ADB", "Test"
            )
            for index in range(30)
        )
        result = CommandCompletionService(specs=specs, visible_limit=8).suggest("adb")
        self.assertEqual(len(result.suggestions), 8)
        self.assertEqual(result.total_count, 30)

    def test_empty_is_hidden_automatically_and_available_manually(self):
        hidden = self.service.suggest("")
        manual = self.service.suggest("", manual=True)
        self.assertEqual(hidden.mode, CompletionMode.HIDDEN)
        self.assertFalse(hidden.suggestions)
        self.assertEqual(manual.mode, CompletionMode.MANUAL)
        self.assertTrue(manual.suggestions)

    def test_unfinished_quotes_do_not_crash_or_expand(self):
        parsed = parse_partial_command('  adb install "C:\\My App')
        self.assertEqual(parsed.unfinished_quote, '"')
        self.assertEqual(parsed.replacement_start, 2)
        self.assertIn("C:My App", parsed.tokens)

    def test_replacement_preserves_unaffected_text_and_leading_space(self):
        source = "  adb re --transport-id 7"
        result = self.service.suggest(source, cursor=8)
        value, cursor = result.suggestions[0].apply(source)
        self.assertTrue(value.startswith("  adb "))
        self.assertTrue(value.endswith(" --transport-id 7"))
        self.assertEqual(cursor, 2 + len(result.suggestions[0].command_text))

    def test_selected_serial_uses_only_context_and_is_quoted(self):
        context = CommandCompletionContext(
            selected_serial="TCP Device 1", selected_device_state="device",
            platform="posix",
        )
        result = self.service.suggest("adb -s ", context)
        selected = next(
            item for item in result.suggestions
            if item.command_id == "context.selected-device"
        )
        self.assertEqual(selected.reason, "Current selected device")
        self.assertEqual(selected.command_text, "adb -s 'TCP Device 1' ")
        self.assertIn("Selected device", result.context_note)

    def test_no_context_provider_or_device_query_is_called(self):
        class Trap:
            def __getattr__(self, name):
                raise AssertionError(f"unexpected manager access: {name}")

        result = self.service.suggest("adb", CommandCompletionContext())
        self.assertTrue(result.suggestions)
        self.assertNotIn(Trap(), result.suggestions)

    def test_selected_target_is_quoted_for_posix_and_windows(self):
        query = "frida -H 127.0.0.1:27042 -n "
        posix = CommandCompletionContext(
            selected_target="Fixture App", platform="posix"
        )
        windows = CommandCompletionContext(
            selected_target="Fixture App", platform="nt"
        )
        self.assertIn("'Fixture App'", self.commands(query, posix)[0])
        self.assertIn('"Fixture App"', self.commands(query, windows)[0])

    def test_placeholder_is_removed_and_cursor_stops_at_required_value(self):
        result = self.service.suggest("adb install")
        suggestion = next(
            item for item in result.suggestions if item.command_id == "adb.install"
        )
        self.assertEqual(suggestion.command_text, "adb install ")
        self.assertEqual(suggestion.placeholders, ("apk",))
        self.assertNotIn("<apk>", suggestion.command_text)
        value, cursor = suggestion.apply("adb install")
        self.assertEqual(value, "adb install ")
        self.assertEqual(cursor, len(value))

    def test_tool_unavailable_is_explanatory_only(self):
        context = CommandCompletionContext(
            tool_availability=(("frida-ps", False),)
        )
        result = self.service.suggest("frida-p", context)
        self.assertIn("Tool unavailable", result.suggestions[0].description)

    def test_common_prefix_is_stable(self):
        result = self.service.suggest("adb re")
        self.assertTrue(result.common_prefix.startswith("adb re"))
        self.assertTrue(
            all(item.command_text.startswith(result.common_prefix) for item in result.suggestions)
        )


if __name__ == "__main__":
    unittest.main()
