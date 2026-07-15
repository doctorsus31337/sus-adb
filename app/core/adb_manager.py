import platform
import shutil
import subprocess


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
                text=True
            )

            return result.stdout.strip()

        except Exception as e:
            return str(e)

    def devices(self):
        return self.run("devices")