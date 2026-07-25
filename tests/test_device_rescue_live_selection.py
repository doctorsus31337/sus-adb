import tempfile
import unittest
from pathlib import Path

from app.core.device import Device
from app.core.device_manager import DeviceManager
from app.core.device_recovery_service import DeviceRecoveryService, RemoteRecoveryEntry
from app.core.host_state import HostStateStore, snapshot_from_runtime
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.host_workspace import (
    HostWorkspaceBinding,
    resolve_host_workspace,
)
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore


class FakeADB:
    def __init__(self, batches):
        self.batches = iter(batches)

    def devices(self, *, enrich=True):
        return next(self.batches)


class RecordingRecoveryBackend:
    def __init__(self):
        self.calls = []

    def state(self, serial):
        self.calls.append(("state", serial))
        return "device"

    def resolve_path(self, serial, path):
        self.calls.append(("resolve", serial))
        return "/storage/emulated/0"

    def identity(self, serial):
        self.calls.append(("identity", serial))
        return "user=0"

    def inventory(self, serial, path, *, depth, limit):
        self.calls.append(("inventory", serial))
        return (
            RemoteRecoveryEntry("/storage/emulated/0/DCIM", "directory", 0),
            RemoteRecoveryEntry("/storage/emulated/0/DCIM/photo.jpg", "file", 4),
        )

    def pull(self, serial, source, destination):
        self.calls.append(("pull", serial))
        Path(destination).write_bytes(b"data")
        return SimpleNamespace(ok=True, output="")


class DeviceRescueLiveSelectionTests(unittest.TestCase):
    @staticmethod
    def publish(devices, host_state, lifecycle="test"):
        return host_state.publish(
            snapshot_from_runtime(devices, lifecycle=lifecycle)
        )

    def test_real_main_state_path_and_backend_keep_the_exact_serial(self):
        device = Device("SERIAL-A", "device", model="Pixel A")
        devices = DeviceManager(FakeADB(((device,),)))
        host_state = HostStateStore()
        devices.refresh()
        self.assertIsNone(devices.selected_serial)
        devices.select(device.serial)
        self.publish(devices, host_state, "device-selected")

        with tempfile.TemporaryDirectory() as directory:
            store = PluginStore(Path(directory) / "plugins")
            plugins = PluginManager(
                store,
                PluginTrustStore(store.root / "state" / "trust.json"),
                ContributionRegistry(),
                auto_refresh=False,
                host_state=host_state,
            )
            rescue = Path(__file__).parents[1] / "plugins/official/device_rescue_recovery"
            installed = plugins.install(rescue)
            self.assertTrue(installed.ok)
            plugin_id = installed.manifest.plugin_id
            self.assertTrue(
                plugins.approve(
                    plugin_id,
                    installed.manifest.requested_capabilities,
                    confirmed=True,
                ).ok
            )
            context = plugins.plugin_context(plugin_id)
            self.assertEqual(context.selected_device["serial"], "SERIAL-A")
            self.assertIsInstance(context.devices, tuple)

            backend = RecordingRecoveryBackend()
            service = DeviceRecoveryService(
                backend, selected_serial_provider=lambda: devices.selected_serial
            )
            scan = service.scan_shared_storage(context.selected_device["serial"])
            self.assertTrue(scan.ok)
            self.assertTrue(backend.calls)
            self.assertEqual({serial for _name, serial in backend.calls}, {"SERIAL-A"})
            plan = service.build_plan(
                scan, ("/storage/emulated/0/DCIM",), directory
            )
            devices.selected_serial = None
            interrupted = service.execute(plan)
            self.assertTrue(interrupted.interrupted)
            self.assertFalse(any(name == "pull" for name, _serial in backend.calls))

    def test_selection_timing_refresh_states_and_no_automatic_selection(self):
        a = Device("A", "device", model="A")
        b = Device("B", "device", model="B")
        unauthorized = Device("U", "unauthorized")
        offline = Device("O", "offline")
        devices = DeviceManager(
            FakeADB(((a, b, unauthorized, offline), (a, b), (b,), ()))
        )
        host_state = HostStateStore()
        received = []
        host_state.subscribe(
            "test", lambda snapshot: received.append(snapshot), replay=False
        )

        devices.refresh()
        self.publish(devices, host_state, "refresh-before-selection")
        self.assertIsNone(devices.selected_serial)
        self.assertEqual(host_state.snapshot().adb_state, "available")
        devices.select("A")
        self.publish(devices, host_state, "selected-after-addon-load")
        self.assertEqual(received[-1].selected_serial, "A")

        devices.refresh()
        self.publish(devices, host_state, "same-serial-refresh")
        self.assertEqual(host_state.snapshot().selected_serial, "A")
        devices.refresh()
        self.publish(devices, host_state, "selection-disappeared")
        self.assertEqual(host_state.snapshot().selected_serial, "")
        self.assertEqual(
            tuple(device.serial for device in host_state.snapshot().devices), ("B",)
        )
        devices.refresh()
        self.publish(devices, host_state, "disconnected")
        self.assertEqual(host_state.snapshot().adb_state, "unavailable")
        self.assertFalse(unauthorized.authorized)
        self.assertFalse(offline.usable)

    def test_legacy_contribution_uses_capability_gated_host_binding(self):
        bindings = {
            "device-rescue.panel": HostWorkspaceBinding(
                lambda parent: parent, "read-selected-device", True
            )
        }
        binding,error = resolve_host_workspace(
            bindings,
            contribution_id="device-rescue.panel",
            approved_capabilities=("read-selected-device",),
        )
        self.assertIsNotNone(binding)
        self.assertFalse(error)
        self.assertTrue(binding.device_selector)

        denied,error = resolve_host_workspace(
            bindings,
            contribution_id="device-rescue.panel",
            approved_capabilities=(),
        )
        self.assertIsNone(denied)
        self.assertIn("read-selected-device", error)


if __name__ == "__main__":
    unittest.main()
