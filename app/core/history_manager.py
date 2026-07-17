class HistoryManager:

    def __init__(self):

        self.history = []
        self.index = -1

    def add(self, command):

        command = command.strip()

        if not command:
            return

        if not self.history or self.history[-1] != command:
            self.history.append(command)

        self.index = len(self.history)

    def previous(self):

        if not self.history:
            return ""

        self.index = max(0, self.index - 1)

        return self.history[self.index]

    def next(self):

        if not self.history:
            return ""

        self.index = min(len(self.history), self.index + 1)

        if self.index >= len(self.history):
            return ""

        return self.history[self.index]