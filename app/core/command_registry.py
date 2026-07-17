class CommandRegistry:

    COMMANDS = {
        "SUS-ADB": [
            "help",
            "clear",
            "exit"
        ],

        "ADB": [
            "adb devices",
            "adb shell",
            "adb reboot",
            "adb reboot recovery",
            "adb reboot bootloader",
            "adb install app.apk",
            "adb uninstall com.example.app",
            "adb push local_file /sdcard/",
            "adb pull /sdcard/file.txt"
        ],

        "FRIDA": [
            "frida-ps -U",
            "frida-ps -Uai",
            "frida -U -n AppName",
            "frida -U -f com.example.app"
        ],

        "OBJECTION": [
            "objection -g com.example.app explore",
            "objection -S socket -n AppName start"
        ]
    }

    @classmethod
    def all_commands(cls):

        commands = []

        for group in cls.COMMANDS.values():
            commands.extend(group)

        return commands

    @classmethod
    def grouped(cls):
        return cls.COMMANDS