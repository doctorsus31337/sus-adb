"""Device discovery and selection state."""

from __future__ import annotations

from app.core.adb_manager import ADBManager
from app.core.device import Device
from app.core.device_cache import DeviceCache


class DeviceManager:
    def __init__(self, adb: ADBManager | None = None):
        self.adb = adb or ADBManager()
        self.cache = DeviceCache()
        self.selected_serial: str | None = None

    def refresh(self, *, enrich: bool = True) -> list[Device]:
        devices = self.adb.devices(enrich=enrich)
        self.cache.update(devices)

        serials = {device.serial for device in devices}
        if self.selected_serial not in serials:
            self.selected_serial = devices[0].serial if devices else None
        return devices

    def all(self) -> list[Device]:
        return list(self.cache.all())

    def select(self, serial: str) -> Device | None:
        for device in self.cache.all():
            if device.serial == serial:
                self.selected_serial = serial
                return device
        return None

    @property
    def selected(self) -> Device | None:
        if self.selected_serial is None:
            return None
        return self.select(self.selected_serial)
