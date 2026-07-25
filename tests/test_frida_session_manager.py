import unittest

from app.core.command_result import CommandResult
from app.core.frida_manager import FridaDiagnosis
from app.core.frida_session_manager import FridaSessionManager
from app.core.frida_target import FridaTarget, TargetType


class FakeTerminal:
    def __init__(self):
        self.commands = []

    def launch(self, command):
        self.commands.append(tuple(command))
        return CommandResult.from_command(command, 0, stdout="launched")


class FakeFrida:
    def __init__(self, running=True, forwarding=True, mismatch=False):
        self.running = running
        self.forwarding = forwarding
        self.mismatch = mismatch
        self.serials = []

    def diagnose(self, serial):
        self.serials.append(serial)
        return FridaDiagnosis(
            serial, True, True, self.running, "/data/local/tmp/frida-server",
            "17.1.0" if self.mismatch else "16.2.1", "16.2.1",
            not self.mismatch, self.forwarding, self.forwarding,
            self.running and self.forwarding,
        )


APP = FridaTarget("Example App", "com.example.app", 42, TargetType.APPLICATION, True)
PROCESS = FridaTarget("System UI", None, 77, TargetType.PROCESS, True)


class FridaSessionManagerTests(unittest.TestCase):
    def make_manager(self, frida=None, terminal=None, frida_path="/tools/frida", trace_path="/tools/frida-trace"):
        return FridaSessionManager(
            frida or FakeFrida(), terminal or FakeTerminal(),
            frida_path=frida_path, frida_trace_path=trace_path,
        )

    def test_attach_by_identifier_pid_spawn_and_trace(self):
        manager = self.make_manager()
        self.assertEqual(manager.build_attach_command(APP)[-2:], ("-n", "com.example.app"))
        self.assertEqual(manager.build_pid_command(PROCESS)[-2:], ("-p", "77"))
        self.assertEqual(manager.build_spawn_command(APP)[-2:], ("-f", "com.example.app"))
        self.assertEqual(manager.build_trace_command(APP, "open*")[-2:], ("-i", "open*"))

    def test_missing_executable_target_and_pid(self):
        manager = self.make_manager(frida_path="")
        self.assertFalse(manager.readiness("SERIAL", APP).ready)
        self.assertFalse(manager.readiness("SERIAL", None).ready)
        with self.assertRaises(ValueError):
            manager.build_attach_command(None)
        with self.assertRaises(ValueError):
            manager.build_pid_command(APP.__class__("App", "com.app", None, TargetType.APPLICATION, False))

    def test_forwarding_and_server_unavailable(self):
        no_forward = self.make_manager(frida=FakeFrida(forwarding=False)).readiness("SERIAL", APP)
        self.assertIn("forwarding", " ".join(no_forward.errors))
        no_server = self.make_manager(frida=FakeFrida(running=False)).readiness("SERIAL", APP)
        self.assertIn("not running", " ".join(no_server.errors))

    def test_version_mismatch_is_warning_and_names_newer_side(self):
        readiness = self.make_manager(frida=FakeFrida(mismatch=True)).readiness("SERIAL", APP)
        self.assertTrue(readiness.ready)
        self.assertIn("Host Frida is newer", readiness.warning)

    def test_launch_uses_injected_terminal(self):
        terminal = FakeTerminal()
        manager = self.make_manager(terminal=terminal)
        result = manager.launch(manager.build_attach_command(APP))
        self.assertTrue(result.ok)
        self.assertEqual(terminal.commands[0][-1], "com.example.app")

    def test_explicit_launch_methods_and_repl_use_terminal(self):
        terminal = FakeTerminal()
        manager = self.make_manager(terminal=terminal)
        manager.launch_attach(APP)
        manager.launch_pid(PROCESS)
        manager.launch_spawn(APP)
        manager.launch_trace(APP, "open*")
        manager.launch_repl()
        self.assertEqual(len(terminal.commands), 5)
        self.assertEqual(terminal.commands[-1], ("/tools/frida", "-H", "127.0.0.1:27042"))


if __name__ == "__main__":
    unittest.main()
