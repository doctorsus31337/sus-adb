"""Read-only, selectable transcript for the integrated Console workspace."""

from __future__ import annotations

from app.gui.read_only_text import ReadOnlyTextView


class ConsoleOutput(ReadOnlyTextView):
    """Host-owned transcript with controlled writes and instance-scoped input."""

    def __init__(self, parent, *, handoff=None, initial_text="", **kwargs):
        self._handoff = handoff
        super().__init__(
            parent,
            initial_text=initial_text,
            keyboard_scroll=False,
            **kwargs,
        )

    def append(self, text):
        value = str(text)

        def write():
            super(ConsoleOutput, self).insert("end", value)
            self.see("end")

        return self._mutate(write)

    def replace(self, text):
        value = str(text)

        def write():
            super(ConsoleOutput, self).delete("1.0", "end")
            super(ConsoleOutput, self).insert("end", value)
            self.see("end")

        return self._mutate(write)

    def _key_pressed(self, event):
        character = getattr(event, "char", "")
        try:
            state = int(getattr(event, "state", 0))
        except (TypeError, ValueError):
            state = self._SHORTCUT_MODIFIERS
        if (
            len(character) != 1
            or not character.isprintable()
            or state & self._SHORTCUT_MODIFIERS
        ):
            return None
        if self._handoff is not None:
            self._handoff(character)
        return "break"

    def close(self):
        self._handoff = None
        super().close()
