"""Reusable read-only, selectable, and scrollable text surfaces."""

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


class ReadOnlyTextView(ctk.CTkTextbox):
    """Host-owned display text with controlled writes and scoped input."""

    _SHORTCUT_MODIFIERS = (
        0x0004 | 0x0008 | 0x0010 | 0x0020 | 0x0040 | 0x0080
    )

    def __init__(self, parent, *, initial_text="", keyboard_scroll=True, **kwargs):
        super().__init__(parent, **kwargs)
        self._closed = False
        self.bindings = ScopedEventBindings()
        inner = self._textbox
        self.scroll_router = ScopedScrollRouter(
            self,
            inner,
            owner=inner,
            keyboard=keyboard_scroll,
            scroll_units=3,
            visible=lambda: bool(self.winfo_ismapped()),
        )
        for sequence, callback in (
            ("<KeyPress>", self._key_pressed),
            ("<Control-c>", self.copy_selection),
            ("<Control-C>", self.copy_selection),
            ("<Control-a>", self.select_all),
            ("<Control-A>", self.select_all),
            ("<Control-x>", self._block_edit),
            ("<Control-X>", self._block_edit),
            ("<Control-v>", self._block_edit),
            ("<Control-V>", self._block_edit),
            ("<<Cut>>", self._block_edit),
            ("<<Paste>>", self._block_edit),
            ("<Button-2>", self._block_edit),
        ):
            self.bindings.bind(inner, sequence, callback)
        super().configure(state="disabled")
        if initial_text:
            self.replace(initial_text)

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
            super().configure(state="normal")
            return operation()
        finally:
            super().configure(state="disabled")

    def append(self, text):
        value = str(text)
        return self._mutate(
            lambda: super(ReadOnlyTextView, self).insert("end", value)
        )

    def replace(self, text):
        value = str(text)

        def write():
            super(ReadOnlyTextView, self).delete("1.0", "end")
            super(ReadOnlyTextView, self).insert("1.0", value)

        return self._mutate(write)

    def clear(self):
        return self.replace("")

    def read(self):
        return self.get("1.0", "end")

    def insert(self, index, text, *tags):
        value = str(text)
        return self._mutate(
            lambda: super(ReadOnlyTextView, self).insert(index, value, *tags)
        )

    def delete(self, index1, index2=None):
        return self._mutate(
            lambda: super(ReadOnlyTextView, self).delete(index1, index2)
        )

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
        return "break"

    def _key_pressed(self, event):
        character = getattr(event, "char", "")
        try:
            state = int(getattr(event, "state", 0))
        except (TypeError, ValueError):
            state = self._SHORTCUT_MODIFIERS
        if (
            len(character) == 1
            and character.isprintable()
            and not state & self._SHORTCUT_MODIFIERS
        ):
            return "break"
        return None

    def focus_for_reading(self):
        return safe_focus(self._textbox)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.scroll_router.close()
        self.bindings.close()

    def destroy(self):
        self.close()
        super().destroy()
