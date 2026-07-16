"""
sus-adb
ADB Manager

Handles all communication with Android Debug Bridge.
"""

import shutil
import subprocess


class ADBManager:

    def __init__(self):

        self.adb = shutil.which("adb")

    ########################################################

    def exists(self):

        return self.adb is not None

    ########################################################

    def run(self, args):

        if not self.exists():

            return ""

        result = subprocess.run(
            ["adb"] + args,
            capture_output=True,
            text=True
        )

        return result.stdout.strip()

    ########################################################

    def devices(self):

        output = self.run(["devices"])

        devices = []

        for line in output.splitlines()[1:]:

            if "\tdevice" in line:

                devices.append(line.split()[0])

        return devices

    ########################################################

    def getprop(self, serial, prop):

        return self.run([
            "-s",
            serial,
            "shell",
            "getprop",
            prop
        ])

    ########################################################

    def battery_level(self, serial):

        output = self.run([
            "-s",
            serial,
            "shell",
            "dumpsys",
            "battery"
        ])

        for line in output.splitlines():

            if "level:" in line:

                return line.split(":")[1].strip() + "%"

        return "Unknown"

    ########################################################

    def get_device_info(self, serial):

        return {

            "Serial": serial,

            "Manufacturer":
                self.getprop(serial, "ro.product.manufacturer"),

            "Model":
                self.getprop(serial, "ro.product.model"),

            "Android":
                self.getprop(serial, "ro.build.version.release"),

            "SDK":
                self.getprop(serial, "ro.build.version.sdk"),

            "Architecture":
                self.getprop(serial, "ro.product.cpu.abi"),

            "Device":
                self.getprop(serial, "ro.product.device"),

            "Build":
                self.getprop(serial, "ro.build.display.id"),

            "Battery":
                self.battery_level(serial)

        }