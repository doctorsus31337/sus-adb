import tempfile
import unittest
from pathlib import Path

from app.core.host_tool_resolver import HostToolResolver
from app.core.terminal_manager import TerminalManager


class Runner:
    def __init__(self):
        self.commands = []

    def stream(self, command, on_line, **_kwargs):
        self.commands.append(tuple(command))
        on_line("ok")
        return 0


class TerminalManagerTests(unittest.TestCase):
    def test_resolved_path_with_spaces_is_one_argv_element_without_shell(self):
        with tempfile.TemporaryDirectory(prefix="sus adb ") as directory:
            executable = Path(directory) / "frida-ps"
            executable.touch()
            resolver = HostToolResolver({"frida-ps": str(executable)}, which=lambda _name: None)
            logs = []
            manager = TerminalManager(logs.append, resolver=resolver)
            runner = Runner()
            manager.runner = runner
            manager._run("frida-ps -H 127.0.0.1:27042")
            self.assertEqual(
                runner.commands,
                [(str(executable.resolve()), "-H", "127.0.0.1:27042")],
            )

    def test_missing_host_tool_is_actionable_and_not_executed(self):
        logs = []
        manager = TerminalManager(
            logs.append,
            resolver=HostToolResolver(which=lambda _name: None, packaged=True),
        )
        runner = Runner()
        manager.runner = runner
        manager._run("frida-ps -H 127.0.0.1:27042")
        self.assertFalse(runner.commands)
        self.assertIn("configure its executable path", " ".join(logs).lower())


if __name__ == "__main__":
    unittest.main()
