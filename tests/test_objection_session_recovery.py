import unittest

from app.core.command_result import CommandResult
from app.core.frida_manager import ForwardingStatus, ManagedForwardingRepair
from app.core.objection_session_recovery import (
    ObjectionFailureKind,
    ObjectionSessionRecovery,
)


class FakeFrida:
    def __init__(self):
        self.forwarding = ForwardingStatus(
            True,
            True,
            CommandResult.from_command(("adb", "forward", "--list"), 0),
        )
        self.endpoint = CommandResult.from_command(("frida-ps",), 0, stdout="app")
        self.managed = ("tcp:27042", "tcp:27043")
        self.repairs = []

    def forwarding_status(self, _serial):
        return self.forwarding

    def list_processes(self, _serial):
        return self.endpoint

    def managed_forwarding_ports(self, _serial):
        return self.managed

    def repair_managed_forwarding(self, serial):
        self.repairs.append(serial)
        return ManagedForwardingRepair(
            serial,
            self.managed,
            ("tcp:27043",),
            ("tcp:27042",),
        )


class ObjectionRecoveryTests(unittest.TestCase):
    def service(self, *, selected="SERIAL", state="device"):
        frida = FakeFrida()
        recovery = ObjectionSessionRecovery(
            frida,
            selected_serial_provider=lambda: selected,
            adb_state_provider=lambda _serial: state,
        )
        return recovery, frida

    def test_device_gone_preserves_target_history_and_actionable_message(self):
        recovery, _frida = self.service()
        report = recovery.analyze(
            "SERIAL",
            "org.example.app",
            "frida.InvalidOperationError: device is gone",
            command_history=("help", "help android sslpinning"),
        )
        self.assertEqual(report.kind, ObjectionFailureKind.DEVICE_GONE)
        self.assertEqual(report.serial, "SERIAL")
        self.assertEqual(report.target, "org.example.app")
        self.assertEqual(report.command_history[-1], "help android sslpinning")
        self.assertIn("lost its connection", report.message)
        self.assertIn("Reconnect", report.actions)
        self.assertTrue(report.fresh_session_required)

    def test_target_exited_and_endpoint_unreachable_are_distinct(self):
        recovery, frida = self.service()
        exited = recovery.analyze(
            "SERIAL", "org.example.app", "Target process has exited."
        )
        self.assertEqual(exited.kind, ObjectionFailureKind.TARGET_EXITED)
        frida.endpoint = CommandResult.from_command(
            ("frida-ps",), 1, error="connection refused"
        )
        unreachable = recovery.check_connection("SERIAL", "org.example.app")
        self.assertEqual(
            unreachable.kind, ObjectionFailureKind.ENDPOINT_UNREACHABLE
        )
        self.assertFalse(unreachable.endpoint_reachable)
        self.assertTrue(unreachable.forwarding_ready)

    def test_forwarding_missing_and_same_serial_enforcement(self):
        recovery, frida = self.service()
        frida.forwarding = ForwardingStatus(
            True,
            False,
            CommandResult.from_command(("adb", "forward", "--list"), 0),
        )
        missing = recovery.check_connection("SERIAL", "org.example.app")
        self.assertEqual(missing.kind, ObjectionFailureKind.FORWARDING_MISSING)
        other, other_frida = self.service(selected="OTHER")
        repair, report = other.repair_managed_forwarding(
            "SERIAL", "org.example.app"
        )
        self.assertFalse(repair.ok)
        self.assertEqual(other_frida.repairs, [])
        self.assertEqual(report.serial, "SERIAL")

    def test_managed_forwarding_repair_is_explicit_and_bounded_to_owner(self):
        recovery, frida = self.service()
        repair, report = recovery.repair_managed_forwarding(
            "SERIAL", "org.example.app"
        )
        self.assertTrue(repair.ok)
        self.assertEqual(frida.repairs, ["SERIAL"])
        self.assertEqual(repair.repaired_ports, ("tcp:27043",))
        self.assertTrue(report.endpoint_reachable)

    def test_cleanup_destroyed_does_not_hide_preceding_device_gone(self):
        recovery, _frida = self.service()
        report = recovery.analyze(
            "SERIAL",
            "org.example.app",
            "help android sslpinning completed\n"
            "frida.InvalidOperationError: device is gone\n"
            "Unable to run cleanups: script is destroyed",
        )
        self.assertEqual(report.kind, ObjectionFailureKind.DEVICE_GONE)
        cleanup = recovery.analyze(
            "SERIAL",
            "org.example.app",
            "Unable to run cleanups: script is destroyed",
        )
        self.assertEqual(
            cleanup.kind, ObjectionFailureKind.CLEANUP_DESTROYED
        )

    def test_invalid_command_is_not_mislabeled_as_connection_loss(self):
        recovery, _frida = self.service()
        report = recovery.analyze(
            "SERIAL", "org.example.app", "Unknown command: wat"
        )
        self.assertEqual(report.kind, ObjectionFailureKind.COMMAND_ERROR)
        self.assertNotIn("Check Connection", report.actions)

    def test_repeated_trace_is_bounded_and_not_repeated_in_concise_output(self):
        recovery, _frida = self.service()
        details = "device is gone\n" + ("trace line\n" * 5_000)
        report = None
        for _index in range(25):
            report = recovery.analyze("SERIAL", "org.example.app", details)
        self.assertEqual(report.repeat_count, 25)
        self.assertLessEqual(len(report.technical_details), 20_000)
        self.assertNotIn("trace line", report.concise())
        self.assertIn("Repeated occurrence count: 25", report.concise())


if __name__ == "__main__":
    unittest.main()
