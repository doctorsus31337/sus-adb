import shutil


class EnvironmentModule:

    TOOLS = [
        "adb",
        "fastboot",
        "frida",
        "objection"
    ]

    @classmethod
    def check(cls):

        results = {}

        for tool in cls.TOOLS:
            results[tool] = shutil.which(tool) is not None

        return results