import unittest

from app.core.adb_manager import ADBManager
from app.core.command_result import CommandResult


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.commands = []

    def run(self, command, **_kwargs):
        self.commands.append(command)
        stdout = self.outputs.pop(0) if self.outputs else ""
        return CommandResult.from_command(command, 0, stdout=stdout)


class ADBManagerTests(unittest.TestCase):
    def test_parse_devices_keeps_online_offline_and_unauthorized(self):
        output = """List of devices attached
SERIAL1\tdevice product:gta7 model:Galaxy_Tab device:gta7 transport_id:1
SERIAL2\tunauthorized transport_id:2
SERIAL3\toffline transport_id:3
"""
        devices = ADBManager.parse_devices(output)
        self.assertEqual([device.serial for device in devices], ["SERIAL1", "SERIAL2", "SERIAL3"])
        self.assertEqual(devices[0].model, "Galaxy Tab")
        self.assertEqual(devices[1].state, "unauthorized")
        self.assertEqual(devices[2].state, "offline")

    def test_missing_adb_returns_structured_error(self):
        runner = FakeRunner([])
        manager = ADBManager(runner=runner, adb_path="")
        result = manager.run("devices")
        self.assertFalse(result.ok)
        self.assertIn("not found", result.output.lower())
        self.assertEqual(runner.commands, [])


if __name__ == "__main__":
    unittest.main()
