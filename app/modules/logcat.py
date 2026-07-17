import subprocess


class LogcatModule:

    @staticmethod
    def start():

        return subprocess.Popen(

            ["adb", "logcat"],

            stdout=subprocess.PIPE,

            stderr=subprocess.STDOUT,

            text=True

        )

    @staticmethod
    def clear():

        subprocess.run(["adb", "logcat", "-c"])