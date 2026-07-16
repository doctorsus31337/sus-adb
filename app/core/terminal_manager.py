import subprocess
import threading


class TerminalManager:

    def __init__(self, log_callback):

        self.log = log_callback

    def execute(self, command):

        thread = threading.Thread(target=self._run, args=(command,), daemon=True)
        thread.start()

    def _run(self, command):

        self.log(f"[CMD] {command}")

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        for line in process.stdout:
            self.log(line.rstrip())

        process.wait()

        if process.returncode == 0:
            self.log("[OK] Command completed successfully.")
        else:
            self.log(f"[ERROR] Command exited with code {process.returncode}.")