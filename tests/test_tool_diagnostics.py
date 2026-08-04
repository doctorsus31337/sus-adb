import tempfile
import unittest
from pathlib import Path

from app.core.command_result import CommandResult
from app.core.host_tool_resolver import HostToolResolver
from app.core.tool_diagnostics import ToolDiagnostics


class FakeRunner:
    def __init__(self, result=None):
        self.commands = []
        self.result = result

    def run(self, command, **kwargs):
        self.commands.append(tuple(command))
        self.kwargs = kwargs
        return self.result or CommandResult.from_command(command, 0, stdout="16.2.1")


class ToolDiagnosticsTests(unittest.TestCase):
    def test_missing_executable_is_structured(self):
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as directory:
            resolver = HostToolResolver(
                which=lambda _name: None,
                interpreter=Path(directory) / "python",
            )
            diagnostic = ToolDiagnostics(
                runner, resolver=resolver
            ).check("frida")
        self.assertFalse(diagnostic.installed)
        self.assertIn("configure its executable path", diagnostic.error.lower())
        self.assertEqual(runner.commands, [])

    def test_frida_uses_version_flag(self):
        runner = FakeRunner()
        ToolDiagnostics(runner, which=lambda name: f"/tools/{name}").check("frida")
        self.assertEqual(runner.commands, [("/tools/frida", "--version")])

    def test_objection_uses_version_subcommand(self):
        runner = FakeRunner()
        diagnostic = ToolDiagnostics(runner, which=lambda name: f"/tools/{name}").check("objection")
        self.assertEqual(runner.commands, [("/tools/objection", "version")])
        self.assertEqual(runner.kwargs["timeout"], 10)
        self.assertTrue(diagnostic.installed)
        self.assertEqual(diagnostic.status, "healthy")

    def test_present_but_broken_objection_is_unhealthy(self):
        result = CommandResult.from_command(
            ("/tools/objection", "version"), 1,
            stderr="ImportError: cannot import name 'url_quote' from werkzeug.urls",
        )
        diagnostic = ToolDiagnostics(
            FakeRunner(result), which=lambda name: f"/tools/{name}"
        ).check("objection")
        self.assertFalse(diagnostic.installed)
        self.assertEqual(diagnostic.status, "broken")
        self.assertIn("present but its health check failed", diagnostic.error)
        self.assertIn("url_quote", diagnostic.error)

    def test_timed_out_objection_is_distinct(self):
        result = CommandResult.from_command(
            ("/tools/objection", "version"), -1, timed_out=True,
            error="Command timed out after 10 seconds.",
        )
        diagnostic = ToolDiagnostics(
            FakeRunner(result), which=lambda name: f"/tools/{name}"
        ).check("objection")
        self.assertFalse(diagnostic.installed)
        self.assertEqual(diagnostic.status, "timed_out")
        self.assertIn("timed out", diagnostic.error)

    def test_fastboot_uses_bounded_version_flag(self):
        runner = FakeRunner()
        ToolDiagnostics(runner, which=lambda name: f"/tools/{name}").check(
            "fastboot"
        )
        self.assertEqual(runner.commands, [("/tools/fastboot", "--version")])


if __name__ == "__main__":
    unittest.main()
