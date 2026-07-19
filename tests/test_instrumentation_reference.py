import unittest

from app.core.frida_session_manager import FridaSessionManager
from app.core.frida_target import FridaTarget, TargetType
from app.core.instrumentation_reference import (
    FRIDA_REPL_STARTER,
    OBJECTION_REPL_STARTER,
    expand_reference_command,
    filter_reference_commands,
    reference_categories,
    reference_commands,
)


TARGET = FridaTarget(
    "Example App", "com.example.app", 321, TargetType.APPLICATION, True
)


class InstrumentationReferenceTests(unittest.TestCase):
    def test_definitions_are_stable_and_immutable(self):
        first = reference_commands()
        second = reference_commands()
        self.assertIs(first, second)
        self.assertGreaterEqual(len(first), 15)
        self.assertEqual(
            {command.tool for command in first},
            {"Frida CLI", "Frida REPL", "Objection REPL"},
        )
        self.assertEqual(reference_categories(), tuple(sorted(reference_categories(), key=str.casefold)))

    def test_tool_category_and_case_insensitive_search(self):
        java = filter_reference_commands(query="ANDROIDVERSION", tool="frida repl", category="java")
        self.assertEqual(len(java), 1)
        self.assertEqual(java[0].command, "Java.androidVersion")
        objection = filter_reference_commands(tool="Objection REPL")
        self.assertTrue(objection)
        self.assertTrue(all(command.tool == "Objection REPL" for command in objection))

    def test_placeholder_expansion_and_selected_endpoint(self):
        command = next(item for item in reference_commands() if "-p {pid}" in item.command)
        expanded = expand_reference_command(command, TARGET)
        self.assertTrue(expanded.ready)
        self.assertIn("321", expanded.command)
        self.assertIn(FridaSessionManager.ENDPOINT, expanded.command)

    def test_missing_identifier_and_pid_remain_visible(self):
        process = FridaTarget("System UI", None, None, TargetType.PROCESS, True)
        identifier_command = next(item for item in reference_commands() if "-n {identifier}" in item.command)
        identifier = expand_reference_command(identifier_command, process)
        self.assertIn("{identifier}", identifier.command)
        self.assertIn("identifier", identifier.guidance)
        pid_command = next(item for item in reference_commands() if "-p {pid}" in item.command)
        pid = expand_reference_command(pid_command, process)
        self.assertIn("{pid}", pid.command)
        self.assertIn("PID", pid.guidance)

    def test_starter_sequences_and_java_guidance(self):
        self.assertEqual(FRIDA_REPL_STARTER[:4], (
            "Process.id", "Process.arch", "Process.platform", "Java.available"
        ))
        self.assertIn("Java.androidVersion", FRIDA_REPL_STARTER)
        self.assertEqual(OBJECTION_REPL_STARTER[0], "help")
        java_version = next(item for item in reference_commands() if item.command == "Java.androidVersion")
        self.assertIn("Java.available", java_version.caution)

    def test_reference_model_has_no_execution_behavior(self):
        for command in reference_commands():
            self.assertFalse(hasattr(command, "execute"))
            self.assertFalse(hasattr(command, "launch"))


if __name__ == "__main__":
    unittest.main()
