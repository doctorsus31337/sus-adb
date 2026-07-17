from datetime import datetime


class SessionManager:

    def __init__(self):

        self.started = datetime.now()

        self.commands = 0

    def command_executed(self):

        self.commands += 1

    def uptime(self):

        delta = datetime.now() - self.started

        return str(delta).split(".")[0]