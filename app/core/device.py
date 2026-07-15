"""
Device model for SUS-ADB

Represents one connected Android device.
"""


class Device:

    def __init__(
        self,
        serial: str,
        state: str,
    ):

        self.serial = serial
        self.state = state

        #
        # These will be populated later
        #

        self.model = "Unknown"

        self.manufacturer = "Unknown"

        self.android_version = "Unknown"

        self.sdk = "Unknown"

        self.root = False

        self.frida = False

        self.objection = False

        self.cpu = "Unknown"

        self.abi = "Unknown"

        self.selinux = "Unknown"

        self.magisk = False

    def __str__(self):

        return (
            f"{self.serial}"
            f" ({self.state})"
        )