"""
ADB Manager
"""

import shutil
import subprocess


class ADBManager:

    def __init__(self):

        self.adb = shutil.which("adb")

    def exists(self):

        return self.adb is not None

    def devices(self):

        if not self.exists():
            return []

        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True
        )

        devices = []

        for line in result.stdout.splitlines()[1:]:

            if "\tdevice" in line:

                serial = line.split()[0]

                devices.append(serial)

        return devices