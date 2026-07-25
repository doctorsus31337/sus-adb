import tempfile
import unittest
from pathlib import Path

from app.core.command_result import CommandResult
from app.core.frida_manager import FridaManager
from app.core.host_tool_resolver import HostToolResolver
from app.core.tool_diagnostics import ToolDiagnostics


class Runner:
    def __init__(self):
        self.commands = []

    def run(self, command, **_kwargs):
        self.commands.append(tuple(command))
        return CommandResult.from_command(command, 0, stdout="16.2.1")


class ADB:
    def exists(self):
        return True


class HostToolResolverTests(unittest.TestCase):
    def test_active_interpreter_directory_resolves_without_path(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Path(directory) / "frida-ps"
            tool.touch()
            resolver = HostToolResolver(which=lambda _name: None, interpreter=Path(directory) / "python")
            self.assertEqual(resolver.resolve("frida-ps"), str(tool.resolve()))

    def test_windows_scripts_executable_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Path(directory) / "frida-ps.exe"
            tool.touch()
            resolver = HostToolResolver(
                which=lambda _name: None, interpreter=Path(directory) / "python.exe",
                platform_name="nt",
            )
            self.assertEqual(resolver.resolve("frida-ps"), str(tool.resolve()))

    def test_configured_path_overrides_path_and_preserves_spaces(self):
        with tempfile.TemporaryDirectory(prefix="sus adb ") as directory:
            configured = Path(directory) / "frida ps"
            configured.touch()
            resolver = HostToolResolver(
                {"frida-ps": str(configured)}, which=lambda _name: "/path/frida-ps"
            )
            runner = Runner()
            diagnostic = ToolDiagnostics(runner, resolver=resolver).check("frida-ps")
            self.assertEqual(diagnostic.executable_path, str(configured.resolve()))
            self.assertEqual(runner.commands[0][0], str(configured.resolve()))
            self.assertEqual(len(runner.commands[0]), 2)

    def test_diagnostics_and_discovery_share_absolute_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Path(directory) / "frida-ps"
            tool.touch()
            resolver = HostToolResolver(which=lambda _name: None, interpreter=Path(directory) / "python")
            runner = Runner()
            diagnostic = ToolDiagnostics(runner, resolver=resolver).check("frida-ps")
            manager = FridaManager(ADB(), runner, frida_path="", resolver=resolver)
            manager.list_processes("SERIAL")
            self.assertEqual(runner.commands[-1], (diagnostic.executable_path, "-H", "127.0.0.1:27042"))

    def test_packaged_mode_only_uses_configured_external_path(self):
        with tempfile.TemporaryDirectory() as directory:
            packaged_tool = Path(directory) / "frida-ps"
            packaged_tool.touch()
            configured_tool = Path(directory) / "external" / "frida-ps"
            configured_tool.parent.mkdir()
            configured_tool.touch()
            no_config = HostToolResolver(
                which=lambda _name: None, interpreter=Path(directory) / "sus-adb",
                packaged=True,
            )
            self.assertIsNone(no_config.resolve("frida-ps"))
            configured = HostToolResolver(
                {"frida-ps": str(configured_tool)}, which=lambda _name: None,
                interpreter=Path(directory) / "sus-adb", packaged=True,
            )
            self.assertEqual(configured.resolve("frida-ps"), str(configured_tool.resolve()))

    def test_missing_configured_tool_is_actionable(self):
        resolver = HostToolResolver({"objection": "/missing/objection"}, which=lambda _name: None)
        diagnostic = ToolDiagnostics(Runner(), resolver=resolver).check("objection")
        self.assertFalse(diagnostic.installed)
        self.assertIn("does not exist", diagnostic.error)


if __name__ == "__main__":
    unittest.main()
