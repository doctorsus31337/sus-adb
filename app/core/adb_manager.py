"""
ADB Manager

Handles all communication with adb.
"""

import platform
import shutil
import subprocess

from app.core.device import Device


class ADBManager:

    def __init__(self):

        self.adb_path = self.find_adb()

    def find_adb(self):

        adb = shutil.which("adb")

        if adb:
            return adb

        if platform.system() == "Windows":

            possible = [

                r"C:\Android\platform-tools\adb.exe",

                r"C:\platform-tools\adb.exe",

            ]

            for path in possible:

                if shutil.os.path.exists(path):

                    return path

        return "adb"

    def run(self, *args):

        command = [self.adb_path]

        command.extend(args)

        try:

            result = subprocess.run(

                command,

                capture_output=True,

                text=True,

            )

            return result.stdout

        except Exception as e:

            return str(e)

    def devices(self):

        output = self.run("devices")

        devices = []

        lines = output.splitlines()

        for line in lines:

            line = line.strip()

            if not line:

                continue

            if line.startswith("List of devices"):

                continue

            parts = line.split()

            if len(parts) < 2:

                continue

            serial = parts[0]

            state = parts[1]

            devices.append(

                Device(

                    serial=serial,

                    state=state,

                )

            )

        return devices