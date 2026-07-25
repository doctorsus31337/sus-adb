"""Connected Android device model used throughout SUS-ADB."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Device:
    serial: str
    state: str = "unknown"
    model: str = "Unknown"
    manufacturer: str = "Unknown"
    android_version: str = "Unknown"
    sdk: str = "Unknown"
    abi: str = "Unknown"
    product: str = "Unknown"
    device_name: str = "Unknown"
    transport_id: str = ""
    battery: str = "Unknown"
    root: bool | None = None
    frida: bool | None = None

    @property
    def connected(self) -> bool:
        return self.state == "device"

    @property
    def authorized(self) -> bool:
        return self.state in {"device", "recovery", "sideload"}

    @property
    def usable(self) -> bool:
        return self.state in {"device", "recovery", "sideload"}

    @property
    def connection_mode(self) -> str:
        return {
            "device": "ADB",
            "recovery": "Recovery ADB",
            "sideload": "ADB Sideload",
            "bootloader": "Bootloader",
            "fastbootd": "Fastbootd",
        }.get(self.state, self.state.title() if self.state else "Unknown")

    @property
    def display_name(self) -> str:
        pieces = [piece for piece in (self.manufacturer, self.model) if piece and piece != "Unknown"]
        return " ".join(pieces) or self.serial

    def __str__(self) -> str:
        return f"{self.display_name} [{self.serial}] — {self.state}"
