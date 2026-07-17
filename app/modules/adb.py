import subprocess


class ADBModule:

    @staticmethod
    def devices():

        result = subprocess.run(

            ["adb", "devices"],

            capture_output=True,

            text=True

        )

        return result.stdout

    @staticmethod
    def reboot():

        subprocess.run(["adb", "reboot"])

    @staticmethod
    def shell():

        subprocess.run(["adb", "shell"])