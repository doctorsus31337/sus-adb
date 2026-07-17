import subprocess


class ADBModule:

    def __init__(self, terminal):
        self.terminal = terminal

    def run(self, *args):
        cmd = ["adb", *args]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()

        if result.stderr:
            output += "\n" + result.stderr.strip()

        return output

    def devices(self):
        return self.run("devices")

    def shell(self, command=""):
        if command:
            return self.run("shell", command)
        return self.run("shell")

    def reboot(self):
        return self.run("reboot")

    def recovery(self):
        return self.run("reboot", "recovery")

    def bootloader(self):
        return self.run("reboot", "bootloader")

    def logcat(self):
        return self.run("logcat", "-d")

    def version(self):
        return self.run("version")