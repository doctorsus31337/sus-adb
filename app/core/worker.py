"""
Background worker thread.

Runs long operations without freezing the GUI.
"""

import threading


class BackgroundWorker(threading.Thread):

    def __init__(self, target, callback=None):
        super().__init__(daemon=True)

        self.target = target
        self.callback = callback

    def run(self):

        result = self.target()

        if self.callback:
            self.callback(result)