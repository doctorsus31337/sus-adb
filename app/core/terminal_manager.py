"""
Embedded terminal manager.

Runs subprocesses and streams stdout back to the GUI.
"""

import subprocess
import threading


class TerminalManager:

    def __init__(self, log_callback):

        self.log = log_callback


    def execute(self, command):

        thread = threading.Thread(
            target=self._run,
            args=(command,),
            daemon=True
        )

        thread.start()


    def _run(self, command):

        self.log(f"> {command}")

        process = subprocess.Popen(

            command,

            shell=True,

            stdout=subprocess.PIPE,

            stderr=subprocess.STDOUT,

            universal_newlines=True

        )

        for line in process.stdout:

            self.log(
                line.rstrip()
            )

        process.wait()

        self.log(
            f"[Process exited with code {process.returncode}]"
        )