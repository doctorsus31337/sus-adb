import unittest

from app.core.device import Device
from app.core.device_manager import DeviceManager


class FakeADB:
    def __init__(self, batches):
        self.batches = iter(batches)

    def devices(self, *, enrich=True):
        return next(self.batches)


class DeviceManagerTests(unittest.TestCase):
    def test_refresh_never_silently_selects_and_preserves_explicit_serial(self):
        first = [Device("A", "device"), Device("B", "offline")]
        second = [Device("A", "device"), Device("B", "device")]
        manager = DeviceManager(FakeADB((first, second)))
        manager.refresh()
        self.assertIsNone(manager.selected)
        self.assertEqual(manager.select("B").serial, "B")
        manager.refresh()
        self.assertEqual(manager.selected.serial, "B")

    def test_disappeared_selection_is_cleared_without_switching(self):
        manager = DeviceManager(
            FakeADB(
                (
                    [Device("A", "device"), Device("B", "device")],
                    [Device("A", "device")],
                )
            )
        )
        manager.refresh()
        manager.select("B")
        manager.refresh()
        self.assertIsNone(manager.selected)
        self.assertIsNone(manager.selected_serial)

    def test_connection_states_are_explicit(self):
        self.assertTrue(Device("A", "recovery").usable)
        self.assertTrue(Device("A", "sideload").usable)
        self.assertFalse(Device("A", "unauthorized").authorized)
        self.assertFalse(Device("A", "offline").usable)
        self.assertEqual(Device("A", "fastbootd").connection_mode, "Fastbootd")
