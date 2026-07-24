import unittest

from app.core.host_state import DeviceState, HostStateSnapshot, HostStateStore
from app.plugins.plugin_api import PluginAPI


class HostStateTests(unittest.TestCase):
    def test_snapshots_are_immutable_and_stale_updates_are_ignored(self):
        store = HostStateStore()
        current = store.publish(
            HostStateSnapshot(
                selected_device=DeviceState("SERIAL", "Pixel", state="device"),
                devices=(DeviceState("SERIAL", "Pixel", state="device"),),
                adb_state="device",
                generation=5,
            )
        )
        stale = store.publish(
            HostStateSnapshot(
                selected_device=DeviceState("OTHER", state="device"),
                generation=4,
            )
        )
        self.assertIs(stale, current)
        self.assertEqual(store.snapshot().selected_serial, "SERIAL")

        context = PluginAPI("test", ("read-selected-device",), host_state=store).context()
        with self.assertRaises(TypeError):
            context.selected_device["serial"] = "changed"
        self.assertIsInstance(context.devices, tuple)

    def test_subscriptions_are_unique_marshaled_and_owned(self):
        dispatched = []
        received = []
        store = HostStateStore(lambda callback, *args: dispatched.append((callback, args)))

        def callback(snapshot):
            received.append(snapshot.generation)

        first = store.subscribe("window", callback, replay=False)
        second = store.subscribe("window", callback, replay=False)
        self.assertEqual(store.subscription_count("window"), 1)
        store.publish(HostStateSnapshot(lifecycle="refresh"))
        self.assertFalse(received)
        for fn, args in dispatched:
            fn(*args)
        self.assertEqual(received, [1])
        second.cancel()
        self.assertEqual(store.subscription_count("window"), 0)
        first.cancel()

    def test_plugin_subscription_ignores_queued_update_after_close(self):
        dispatched = []
        store = HostStateStore(lambda callback, *args: dispatched.append((callback, args)))
        api = PluginAPI("owned", host_state=store)
        received = []
        api.subscribe_context(lambda context: received.append(context.generation), replay=False)
        store.publish(HostStateSnapshot(lifecycle="refresh"))
        api.close()
        for fn, args in dispatched:
            fn(*args)
        self.assertEqual(received, [])
        self.assertEqual(store.subscription_count("plugin:owned"), 0)
