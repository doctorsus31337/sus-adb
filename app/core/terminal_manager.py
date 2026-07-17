from app.core.history_manager import HistoryManager
import subprocess
import threading


class TerminalManager:

    PROMPT = "sus-adb >> "

    def __init__(self, log_callback):
        self.cwd = None
        self.log = log_callback
        self.history = HistoryManager()

    def execute(self, command):

        command = command.strip()
        self.history.add(command)
        
        if not command:
            return

        thread = threading.Thread(
            target=self._run,
            args=(command,),
            daemon=True
        )

        thread.start()
        

    def _run(self, command):q
        self.log("")
        self.log(f"{self.PROMPT}{command}")
        self.log("")

        if command.lower() == "cls":
            self.log("\n" * 40)
            return
        if command.lower() == "clear":
            self.log("\n" * 40)
            return

        if command == "devices":
            output = ADBModule.devices()
            self.log(output)
            return

        if command == "logcat":
            self.log("Starting Logcat...")
            LogcatModule.start()
            return

        if command == "clearlog":
            LogcatModule.clear()
            self.log("Logcat buffer cleared.")
            return


        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        if process.stdout:

            for line in iter(process.stdout.readline, ""):

                line = line.rstrip()

                if line:
                    self.log(line)

        process.wait()

        self.log("")

        if process.returncode == 0:
            self.log("[✓] Complete")
        else:
            self.log(f"[✗] Exit Code {process.returncode}")

        self.log("")