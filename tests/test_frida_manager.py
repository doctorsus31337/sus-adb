import unittest

from app.core.command_result import CommandResult
from app.core.frida_manager import FridaManager


class FakeRunner:
    def __init__(self, handler=None):
        self.handler = handler
        self.commands = []

    def run(self, command, **kwargs):
        command = tuple(command)
        self.commands.append(command)
        if self.handler:
            return self.handler(command, kwargs)
        return CommandResult.from_command(command, 0)


class FakeADB:
    def __init__(self, handler=None, exists=True):
        self.handler = handler
        self.available = exists
        self.calls = []

    def exists(self):
        return self.available

    def run(self, *args, serial=None, **kwargs):
        self.calls.append((args, serial, kwargs))
        if self.handler:
            return self.handler(args, serial, kwargs)
        return CommandResult.from_command(("adb", *args), 0)


def adb_output(args, serial, _kwargs):
    joined = " ".join(args)
    if "pidof" in joined:
        return CommandResult.from_command(args, 0, stdout="1234")
    if "for f in" in joined:
        return CommandResult.from_command(args, 0, stdout="/data/local/tmp/frida-server")
    if "--version" in joined:
        return CommandResult.from_command(args, 0, stdout="16.2.1")
    if "su -c id" in joined:
        return CommandResult.from_command(args, 0, stdout="uid=0(root)")
    if args[:2] == ("forward", "--list"):
        return CommandResult.from_command(
            args, 0, stdout=f"{serial} tcp:27042 tcp:27042\n{serial} tcp:27043 tcp:27043"
        )
    return CommandResult.from_command(args, 0)


class FridaManagerTests(unittest.TestCase):
    def make_manager(self, adb=None, runner=None):
        return FridaManager(
            adb or FakeADB(adb_output), runner or FakeRunner(),
            frida_path="/tools/frida", frida_ps_path="/tools/frida-ps",
        )

    def test_no_selected_serial(self):
        manager = self.make_manager()
        diagnosis = manager.diagnose(None)
        self.assertIsNone(diagnosis.serial)
        self.assertFalse(diagnosis.reachable)
        self.assertIn("No device", diagnosis.errors[0])

    def test_server_running_and_stopped(self):
        self.assertTrue(self.make_manager().server_running("SERIAL"))

        def stopped(args, _serial, _kwargs):
            return CommandResult.from_command(args, 1)

        self.assertFalse(self.make_manager(adb=FakeADB(stopped)).server_running("SERIAL"))

    def test_version_match_and_mismatch(self):
        host_match = FakeRunner(lambda command, _: CommandResult.from_command(command, 0, stdout="16.2.1"))
        self.assertTrue(self.make_manager(runner=host_match).diagnose("SERIAL").versions_match)
        host_mismatch = FakeRunner(lambda command, _: CommandResult.from_command(command, 0, stdout="17.0.0"))
        self.assertFalse(self.make_manager(runner=host_mismatch).diagnose("SERIAL").versions_match)

    def test_forwarding_missing(self):
        def handler(args, serial, kwargs):
            if args[:2] == ("forward", "--list"):
                return CommandResult.from_command(args, 0, stdout=f"{serial} tcp:27042 tcp:27042")
            return adb_output(args, serial, kwargs)

        status = self.make_manager(adb=FakeADB(handler)).forwarding_status("SERIAL")
        self.assertTrue(status.port_27042)
        self.assertFalse(status.port_27043)

    def test_forwarding_repair_targets_selected_serial(self):
        adb = FakeADB()
        results = self.make_manager(adb=adb).repair_forwarding("SERIAL")
        self.assertTrue(all(result.ok for result in results))
        self.assertEqual(adb.calls[0][0], ("forward", "tcp:27042", "tcp:27042"))
        self.assertEqual(adb.calls[1][0], ("forward", "tcp:27043", "tcp:27043"))
        self.assertEqual([call[1] for call in adb.calls], ["SERIAL", "SERIAL"])

    def test_no_hidden_fallback_to_host_executable(self):
        runner = FakeRunner()
        manager = FridaManager(FakeADB(), runner, frida_path="", frida_ps_path="")
        self.assertFalse(manager.host_version().ok)
        self.assertFalse(manager.list_processes("SERIAL").ok)
        self.assertEqual(runner.commands, [])

    def test_server_already_running_does_not_execute_start(self):
        adb = FakeADB(adb_output)
        result = self.make_manager(adb=adb).start_server("SERIAL")
        self.assertTrue(result.ok)
        self.assertIn("already running", result.stdout.lower())
        self.assertFalse(any("chmod 755" in " ".join(call[0]) for call in adb.calls))

    def test_address_in_use_requires_expected_server_verification(self):
        state = {"started": False}

        def handler(args, serial, kwargs):
            joined = " ".join(args)
            if "chmod 755" in joined:
                state["started"] = True
                return CommandResult.from_command(args, 1, error="Address already in use")
            if "pidof" in joined:
                return CommandResult.from_command(args, 0 if state["started"] else 1, stdout="42" if state["started"] else "")
            return adb_output(args, serial, kwargs)

        result = self.make_manager(adb=FakeADB(handler)).start_server("SERIAL")
        self.assertTrue(result.ok)
        self.assertIn("already running", result.stdout.lower())

    def test_unrelated_address_in_use_remains_failure(self):
        def handler(args, serial, kwargs):
            if "chmod 755" in " ".join(args):
                return CommandResult.from_command(args, 1, error="Address already in use")
            if "pidof" in " ".join(args):
                return CommandResult.from_command(args, 1)
            return adb_output(args, serial, kwargs)

        result = self.make_manager(adb=FakeADB(handler)).start_server("SERIAL")
        self.assertFalse(result.ok)
        self.assertIn("address already in use", result.output.lower())


if __name__ == "__main__":
    unittest.main()
