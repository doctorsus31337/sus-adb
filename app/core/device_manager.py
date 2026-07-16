"""
Device management layer.
"""

from app.core.adb_manager import ADBManager


class DeviceManager:

    def __init__(self):

        self.adb = ADBManager()

        self.devices = []


    def refresh(self):

        self.devices = self.adb.get_devices()

        return self.devices