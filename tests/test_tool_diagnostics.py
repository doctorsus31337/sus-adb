import unittest

from app.core.command_result import CommandResult
from app.core.tool_diagnostics import ToolDiagnostics


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command, **_kwargs):
        self.commands.append(tuple(command))
        return CommandResult.from_command(command, 0, stdout="16.2.1")


class ToolDiagnosticsTests(unittest.TestCase):
    def test_missing_executable_is_structured(self):
        runner = FakeRunner()
        diagnostic = ToolDiagnostics(runner, which=lambda _name: None).check("frida")
        self.assertFalse(diagnostic.installed)
        self.assertIn("not found", diagnostic.error.lower())
        self.assertEqual(runner.commands, [])

    def test_frida_uses_version_flag(self):
        runner = FakeRunner()
        ToolDiagnostics(runner, which=lambda name: f"/tools/{name}").check("frida")
        self.assertEqual(runner.commands, [("/tools/frida", "--version")])

    def test_objection_uses_version_subcommand(self):
        runner = FakeRunner()
        ToolDiagnostics(runner, which=lambda name: f"/tools/{name}").check("objection")
        self.assertEqual(runner.commands, [("/tools/objection", "version")])


if __name__ == "__main__":
    unittest.main()
