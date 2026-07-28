"""Read-only, selectable transcript for the integrated Console workspace."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from app.gui.customtkinter_compat import (
    ScopedEventBindings,
    ScopedScrollRouter,
    safe_focus,
    widget_exists,
)
from app.utils.clipboard import ClipboardManager


class ConsoleOutput(ctk.CTkTextbox):
    """Host-owned transcript with controlled writes and instance-scoped input."""

    _SHORTCUT_MODIFIERS = 0x0004 | 0x0008 | 0x0010 | 0x0020 | 0x0040 | 0x0080

    def __init__(self, parent, *, handoff=None, initial_text="", **kwargs):
        super().__init__(parent, **kwargs)
        self._handoff = handoff
        self._closed = False
        self.bindings = ScopedEventBindings()
        inner = self._textbox
        self.scroll_router = ScopedScrollRouter(
            self,
            inner,
            owner=inner,
            keyboard=False,
            scroll_units=3,
            visible=lambda: bool(self.winfo_ismapped()),
        )
        for sequence, callback in (
            ("<KeyPress>", self._key_pressed),
            ("<Control-c>", self.copy_selection),
            ("<Control-a>", self.select_all),
            ("<Control-x>", self._block_edit),
            ("<Control-v>", self._block_edit),
            ("<<Cut>>", self._block_edit),
            ("<<Paste>>", self._block_edit),
            ("<Button-2>", self._block_edit),
        ):
            self.bindings.bind(inner, sequence, callback)
        self.configure(state="disabled")
        if initial_text:
            self.append(initial_text)

    @property
    def binding_count(self):
        return self.bindings.count + self.scroll_router.count

    @property
    def read_only(self):
        try:
            return self._textbox.cget("state") == "disabled"
        except tk.TclError:
            return True

    def _mutate(self, operation):
        if self._closed or not widget_exists(self):
            return None
        try:
            self.configure(state="normal")
            return operation()
        finally:
            self.configure(state="disabled")

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

    def clear(self):
        return self.replace("")

    def read(self):
        return self.get("1.0", "end")

    def copy_selection(self, _event=None):
        return "break" if ClipboardManager.copy(self) else None

    def select_all(self, _event=None):
        if not widget_exists(self._textbox):
            return "break"
        self._textbox.tag_add("sel", "1.0", "end-1c")
        self._textbox.mark_set("insert", "1.0")
        self._textbox.see("insert")
        return "break"

    @staticmethod
    def _block_edit(_event=None):
        """Explicit paste, cut, and middle-click paste are deterministic no-ops."""
        return "break"

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

    def focus_for_reading(self):
        return safe_focus(self._textbox)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.scroll_router.close()
        self.bindings.close()
        self._handoff = None

    def destroy(self):
        self.close()
        super().destroy()
