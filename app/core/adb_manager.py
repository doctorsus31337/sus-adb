"""Android Debug Bridge backend for SUS-ADB."""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterable

from app.core.command_result import CommandResult
from app.core.command_runner import CommandRunner
from app.core.device import Device


class ADBManager:
    def __init__(self, runner: CommandRunner | None = None, adb_path: str | None = None):
        self.runner = runner or CommandRunner()
        self.adb_path = adb_path or shutil.which("adb")

    def exists(self) -> bool:
        return bool(self.adb_path)

    def run(
        self,
        *args: str,
        serial: str | None = None,
        timeout: float = 30,
    ) -> CommandResult:
        if not self.adb_path:
            return CommandResult.from_command(
                ("adb", *args),
                -1,
                error="ADB was not found in PATH.",
            )

        command = [self.adb_path]
        if serial:
            command.extend(("-s", serial))
        command.extend(str(arg) for arg in args)
        return self.runner.run(command, timeout=timeout)

    def devices(self, *, enrich: bool = True) -> list[Device]:
        result = self.run("devices", "-l", timeout=15)
        if not result.ok and not result.stdout:
            return []

        devices = self.parse_devices(result.stdout)
        if enrich:
            for device in devices:
                if device.connected:
                    self.populate_device(device)
        return devices

    @staticmethod
    def parse_devices(output: str) -> list[Device]:
        devices: list[Device] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("List of devices attached") or line.startswith("*"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            serial, state = parts[0], parts[1]
            metadata: dict[str, str] = {}
            for token in parts[2:]:
                if ":" in token:
                    key, value = token.split(":", 1)
                    metadata[key] = value.replace("_", " ")

            devices.append(
                Device(
                    serial=serial,
                    state=state,
                    model=metadata.get("model", "Unknown"),
                    product=metadata.get("product", "Unknown"),
                    device_name=metadata.get("device", "Unknown"),
                    transport_id=metadata.get("transport_id", ""),
                )
            )
        return devices

    def populate_device(self, device: Device) -> Device:
        props = self.get_properties(
            device.serial,
            {
                "manufacturer": "ro.product.manufacturer",
                "model": "ro.product.model",
                "android_version": "ro.build.version.release",
                "sdk": "ro.build.version.sdk",
                "abi": "ro.product.cpu.abi",
                "product": "ro.product.name",
                "device_name": "ro.product.device",
            },
        )
        for field_name, value in props.items():
            if value:
                setattr(device, field_name, value)

        device.battery = self.battery_level(device.serial)
        device.root = self.has_root(device.serial)
        device.frida = self.frida_server_running(device.serial)
        return device

    def get_properties(self, serial: str, properties: dict[str, str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for field_name, prop_name in properties.items():
            result = self.run("shell", "getprop", prop_name, serial=serial, timeout=8)
            values[field_name] = result.stdout.strip() if result.ok else ""
        return values

    def battery_level(self, serial: str) -> str:
        result = self.run("shell", "dumpsys", "battery", serial=serial, timeout=10)
        match = re.search(r"^\s*level:\s*(\d+)\s*$", result.stdout, flags=re.MULTILINE)
        return f"{match.group(1)}%" if match else "Unknown"

    def has_root(self, serial: str) -> bool:
        result = self.run("shell", "su", "-c", "id", serial=serial, timeout=8)
        return result.ok and "uid=0" in result.stdout

    def frida_server_running(self, serial: str) -> bool:
        result = self.run(
            "shell",
            "su",
            "-c",
            "pidof frida-server",
            serial=serial,
            timeout=8,
        )
        return result.ok and bool(result.stdout.strip())

    def forward_frida_ports(self, serial: str) -> tuple[CommandResult, CommandResult]:
        first = self.run("forward", "tcp:27042", "tcp:27042", serial=serial, timeout=10)
        second = self.run("forward", "tcp:27043", "tcp:27043", serial=serial, timeout=10)
        return first, second

    def start_frida_server(
        self,
        serial: str,
        server_path: str = "/data/local/tmp/frida-server",
    ) -> CommandResult:
        command = f"chmod 755 {server_path} && {server_path} >/dev/null 2>&1 &"
        return self.run("shell", "su", "-c", command, serial=serial, timeout=12)

    def stop_frida_server(self, serial: str) -> CommandResult:
        return self.run(
            "shell",
            "su",
            "-c",
            "pkill -f frida-server",
            serial=serial,
            timeout=10,
        )
