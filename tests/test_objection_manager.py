import unittest

from app.core.command_result import CommandResult
from app.core.frida_manager import FridaDiagnosis
from app.core.objection_manager import ObjectionManager


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command, **_kwargs):
        self.commands.append(tuple(command))
        return CommandResult.from_command(command, 0, stdout="objection: 1.11")


class FakeFrida:
    def __init__(self, reachable=True, forwarding=True):
        self.reachable = reachable
        self.forwarding = forwarding

    def diagnose(self, serial):
        return FridaDiagnosis(
            serial, True, True, True, "/data/local/tmp/frida-server",
            "16.2.1", "16.2.1", True, self.forwarding, self.forwarding,
            self.reachable,
        )


class FakeTerminal:
    def __init__(self, result=None):
        self.commands = []
        self.result = result

    def launch(self, command):
        self.commands.append(tuple(command))
        return self.result or CommandResult.from_command(command, 0, stdout="launched")


class ObjectionManagerTests(unittest.TestCase):
    def make_manager(self, **kwargs):
        return ObjectionManager(
            FakeRunner(), kwargs.pop("frida", FakeFrida()),
            kwargs.pop("terminal", FakeTerminal()), objection_path="/tools/objection",
            which=kwargs.pop("which", lambda _name: None),
            **kwargs,
        )

    def test_empty_target_rejected(self):
        self.assertFalse(ObjectionManager.validate_target("   ").ok)

    def test_socket_attach_and_spawn_commands(self):
        manager = self.make_manager()
        self.assertEqual(
            manager.build_attach_command("com.example.app", "socket"),
            ("/tools/objection", "-S", "socket", "-n", "com.example.app", "start"),
        )
        self.assertEqual(
            manager.build_spawn_command("com.example.app", "socket"),
            ("/tools/objection", "-S", "socket", "-n", "com.example.app", "-s", "start"),
        )

    def test_usb_command_uses_selected_serial(self):
        command = self.make_manager().build_attach_command("com.example.app", "usb", "SERIAL")
        self.assertEqual(command[1:3], ("-S", "SERIAL"))
        self.assertNotIn("-g", command)

    def test_missing_objection(self):
        manager = ObjectionManager(FakeRunner(), FakeFrida(), FakeTerminal(), objection_path="")
        readiness = manager.readiness("SERIAL", "target", "socket")
        self.assertFalse(readiness.ready)
        self.assertFalse(readiness.objection_installed)

    def test_missing_frida_readiness(self):
        readiness = self.make_manager(frida=FakeFrida(reachable=False)).readiness(
            "SERIAL", "target", "usb"
        )
        self.assertFalse(readiness.ready)
        self.assertIn("not reachable", " ".join(readiness.errors))

    def test_no_supported_external_terminal(self):
        failure = CommandResult.from_command(("objection",), -1, error="No supported external terminal was found.")
        result = self.make_manager(terminal=FakeTerminal(failure)).launch_external_session(("objection", "version"))
        self.assertFalse(result.ok)
        self.assertIn("terminal", result.error.lower())

    def test_structured_launch_failure(self):
        failure = CommandResult.from_command(("objection",), -1, error="launch failed")
        manager = self.make_manager(terminal=FakeTerminal(failure))
        result = manager.launch_external_session(("objection", "version"))
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "launch failed")


if __name__ == "__main__":
    unittest.main()
