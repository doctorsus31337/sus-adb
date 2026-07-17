import subprocess
import threading


class TerminalManager:

    PROMPT = "sus-adb > "

    def __init__(self, log_callback):
        self.log = log_callback

    def execute(self, command):

        command = command.strip()

        if not command:
            return

        thread = threading.Thread(
            target=self._run,
            args=(command,),
            daemon=True
        )

        thread.start()

    def _run(self, command):

        self.log("")
        self.log(f"{self.PROMPT}{command}")
        self.log("")

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