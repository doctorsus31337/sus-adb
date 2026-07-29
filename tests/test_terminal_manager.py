import io
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from app.core.command_runner import CommandRunner
from app.core.host_tool_resolver import HostToolResolver
from app.core.command_router import CommandRouter
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

    def test_interactive_route_never_marks_console_busy_or_starts_runner(self):
        logs = []
        routes = []
        manager = TerminalManager(
            logs.append,
            resolver=HostToolResolver(which=lambda _name: None),
            interactive_callback=routes.append,
        )
        runner = Runner()
        manager.runner = runner
        manager.execute("adb -s SERIAL shell")
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].serial, "SERIAL")
        self.assertFalse(manager._active)
        self.assertEqual(runner.commands, [])

    def test_fastboot_uses_validated_route_argv_and_preserves_output(self):
        with tempfile.TemporaryDirectory(prefix="fastboot tools ") as directory:
            executable = Path(directory) / "fastboot"
            executable.touch()
            resolver = HostToolResolver(
                {"fastboot": str(executable)}, which=lambda _name: None
            )
            logs = []
            manager = TerminalManager(logs.append, resolver=resolver)
            runner = Runner()
            manager.runner = runner
            route = manager.router.classify(
                "fastboot -s FB-SERIAL getvar product"
            )
            manager._run(route)
            self.assertEqual(
                runner.commands,
                [
                    (
                        str(executable.resolve()), "-s", "FB-SERIAL",
                        "getvar", "product",
                    )
                ],
            )
            self.assertIn("ok", logs)

    def test_blocked_fastboot_never_runs_or_enters_history(self):
        logs = []
        manager = TerminalManager(
            logs.append,
            resolver=HostToolResolver(which=lambda _name: None, packaged=True),
        )
        runner = Runner()
        manager.runner = runner
        manager.execute("fastboot flash boot boot.img")
        self.assertFalse(runner.commands)
        self.assertEqual(manager.history.entries(), ())
        self.assertIn("not supported", " ".join(logs))

    def test_missing_fastboot_is_actionable_and_not_executed(self):
        logs = []
        manager = TerminalManager(
            logs.append,
            resolver=HostToolResolver(which=lambda _name: None, packaged=True),
        )
        runner = Runner()
        manager.runner = runner
        manager._run("fastboot devices")
        self.assertFalse(runner.commands)
        self.assertIn("configure its executable path", " ".join(logs).lower())

    def test_command_runner_stream_is_structured_shell_false_and_merges_stderr(self):
        process = mock.Mock()
        process.stdout = io.StringIO("getvar result from merged stderr\n")
        process.wait.return_value = 0
        lines = []
        with mock.patch(
            "app.core.command_runner.subprocess.Popen", return_value=process
        ) as popen:
            returncode = CommandRunner().stream(
                ("/tools with spaces/fastboot", "-s", "FB", "getvar", "product"),
                lines.append,
            )
        self.assertEqual(returncode, 0)
        self.assertEqual(lines, ["getvar result from merged stderr"])
        arguments, options = popen.call_args
        self.assertEqual(arguments[0][0], "/tools with spaces/fastboot")
        self.assertIs(options["stderr"], subprocess.STDOUT)
        self.assertFalse(options["shell"])


if __name__ == "__main__":
    unittest.main()
