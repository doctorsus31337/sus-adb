import platform
import sys


class SystemInfo:

    @staticmethod
    def get():

        return {
            "python": sys.version.split()[0],
            "platform": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }