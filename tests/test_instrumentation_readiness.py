import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.command_result import CommandResult
from app.core.instrumentation_readiness import (
    InstrumentationReadinessService,
    ReadinessRoute,
)


class FakeADB:
    def __init__(self):
        self.calls = []
        self.adb_root = False

    def run(self, *args, serial=None, timeout=None):
        self.calls.append((args, serial, timeout))
        if args[:3] == ("shell", "getprop", "ro.product.cpu.abi"):
            return CommandResult.from_command(args, 0, stdout="arm64-v8a")
        if args[:2] == ("shell", "id"):
            return CommandResult.from_command(
                args, 0, stdout="uid=0(root)" if self.adb_root else "uid=2000(shell)"
            )
        if args[:3] == ("shell", "su", "-c") and str(args[3]).startswith("test -e"):
            return CommandResult.from_command(args, 1, stderr="missing")
        return CommandResult.from_command(args, 0, stdout="ok")


class FakeFrida:
    def __init__(self, *, root=True, server=False, reachable=False):
        self.root = root
        self.server = server
        self.reachable = reachable
        self.calls = []

    def root_available(self, serial):
        self.calls.append(("root", serial))
        return self.root

    def diagnose(self, serial):
        self.calls.append(("diagnose", serial))
        return SimpleNamespace(
            root_available=self.root,
            server_path="/data/local/tmp/frida-server" if self.server else None,
            reachable=self.reachable,
            host_version="17.2.1",
            server_version="17.2.1" if self.server else None,
        )

    def repair_forwarding(self, serial):
        self.calls.append(("forward", serial))
        return (
            CommandResult.from_command(("forward", "27042"), 0),
            CommandResult.from_command(("forward", "27043"), 0),
        )

    def list_processes(self, serial):
        self.calls.append(("list", serial))
        return CommandResult.from_command(("frida-ps",), 0, stdout="1 App")

    def stop_server(self, serial):
        self.calls.append(("stop", serial))
        return CommandResult.from_command(("stop",), 0)


class Session:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def permits(self, category):
        return self.allowed and category == "state-changing-testing"


def elf(path, machine=183, size=128):
    data = bytearray(max(size, 64))
    data[:4] = b"\x7fELF"
    data[4] = 2
    data[5] = 1
    data[18:20] = struct.pack("<H", machine)
    path.write_bytes(data)
    return path


class InstrumentationReadinessTests(unittest.TestCase):
    def service(self, **frida_values):
        adb = FakeADB()
        frida = FakeFrida(**frida_values)
        service = InstrumentationReadinessService(
            adb, frida,
            selected_serial_provider=lambda: "SERIAL",
            session_provider=lambda: Session(),
        )
        return service, adb, frida

    def test_all_route_classifications_are_structured(self):
        cases = (
            ({}, ReadinessRoute.UNKNOWN),
            ({"serial": "S", "adb_state": "offline"}, ReadinessRoute.BLOCKED),
            ({"serial": "S", "adb_state": "device", "root_available": True,
              "server_available": True, "endpoint_reachable": True},
             ReadinessRoute.ROOTED_SERVER_READY),
            ({"serial": "S", "adb_state": "device", "root_available": True},
             ReadinessRoute.ROOTED_SERVER_SETUP_AVAILABLE),
            ({"serial": "S", "adb_state": "device", "gadget_available": True,
              "endpoint_reachable": True}, ReadinessRoute.GADGET_READY),
            ({"serial": "S", "adb_state": "device",
              "gadget_preparation_available": True},
             ReadinessRoute.GADGET_PREPARATION_AVAILABLE),
            ({"serial": "S", "adb_state": "device", "debuggable": True},
             ReadinessRoute.DEBUGGABLE_DEVELOPMENT_ROUTE),
            ({"serial": "S", "adb_state": "device", "emulator": True},
             ReadinessRoute.EMULATOR_ROUTE),
            ({"serial": "S", "adb_state": "device"}, ReadinessRoute.ADB_ONLY),
        )
        for values, expected in cases:
            with self.subTest(expected=expected):
                result = InstrumentationReadinessService.classify(**values)
                self.assertEqual(result.route, expected)
                self.assertTrue(result.evidence)
                self.assertTrue(result.next_action)
                self.assertIn("commonly wipes", result.data_loss_risk)

    def test_scan_is_explicit_serial_and_evidence_based(self):
        service, adb, frida = self.service(root=True)
        result = service.assess_device("SERIAL", "device")
        self.assertEqual(
            result.route, ReadinessRoute.ROOTED_SERVER_SETUP_AVAILABLE
        )
        self.assertEqual(adb.calls[0][1], "SERIAL")
        self.assertEqual(frida.calls, [("diagnose", "SERIAL")])

    def test_binary_validation_hash_size_and_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = elf(Path(directory) / "frida server")
            valid = InstrumentationReadinessService.validate_binary(
                binary, "arm64-v8a"
            )
            self.assertTrue(valid.valid)
            self.assertEqual(valid.architecture, "arm64")
            self.assertEqual(len(valid.sha256), 64)
            mismatch = InstrumentationReadinessService.validate_binary(
                binary, "x86_64"
            )
            self.assertFalse(mismatch.valid)
            self.assertIn("does not match", mismatch.errors[0])

    def test_operator_selected_firmware_is_hashed_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware = Path(directory) / "boot image.bin"
            original = b"ANDROID!" + b"\0" * 64
            firmware.write_bytes(original)
            result = InstrumentationReadinessService.inspect_firmware_input(
                firmware
            )
            self.assertEqual(result.classification, "android-boot-image")
            self.assertEqual(len(result.sha256), 64)
            self.assertEqual(firmware.read_bytes(), original)

    def test_preview_never_executes_and_actions_never_chain(self):
        service, adb, frida = self.service(root=True)
        with tempfile.TemporaryDirectory() as directory:
            validation = service.validate_binary(
                elf(Path(directory) / "frida-server"), "arm64"
            )
            preview = service.preview_upload(
                validation, service.DEFAULT_DESTINATION
            )
            self.assertTrue(preview.ok)
            self.assertFalse(adb.calls)
            uploaded = service.upload(
                "SERIAL", validation, service.DEFAULT_DESTINATION,
                confirmed=True,
            )
            self.assertTrue(uploaded.ok)
            self.assertEqual([call[0][0] for call in adb.calls], ["shell", "push"])
            self.assertFalse(any("chmod" in " ".join(call[0]) for call in adb.calls))
            chmod = service.set_executable(
                "SERIAL", service.DEFAULT_DESTINATION, confirmed=True
            )
            self.assertTrue(chmod.ok)
            self.assertIn("chmod 755", adb.calls[-1][0][-1])
            self.assertTrue(all(call[1] == "SERIAL" for call in adb.calls))

    def test_scope_root_same_serial_and_managed_removal_are_enforced(self):
        service, adb, frida = self.service(root=False)
        blocked = service.start(
            "OTHER", service.DEFAULT_DESTINATION, confirmed=True
        )
        self.assertFalse(blocked.ok)
        self.assertIn("currently selected serial", blocked.error)
        blocked = service.start(
            "SERIAL", service.DEFAULT_DESTINATION, confirmed=True
        )
        self.assertFalse(blocked.ok)
        self.assertIn("existing root", blocked.error)
        frida.root = True
        remove = service.remove_managed(
            "SERIAL", service.DEFAULT_DESTINATION, confirmed=True
        )
        self.assertFalse(remove.ok)
        self.assertIn("not uploaded", remove.error)

    def test_no_action_without_confirmation_or_authorized_scope(self):
        service, adb, _frida = self.service(root=True)
        result = service.configure_forwarding("SERIAL")
        self.assertFalse(result.ok)
        self.assertFalse(adb.calls)
        service.session_provider = lambda: Session(False)
        result = service.configure_forwarding("SERIAL", confirmed=True)
        self.assertFalse(result.ok)
        self.assertIn("state-changing-testing", result.error)

    def test_authorized_adb_root_is_accepted_without_su(self):
        service, adb, frida = self.service(root=False)
        adb.adb_root = True
        result = service.configure_forwarding("SERIAL", confirmed=True)
        self.assertTrue(result.ok)
        self.assertIn(("forward", "SERIAL"), frida.calls)


if __name__ == "__main__":
    unittest.main()
