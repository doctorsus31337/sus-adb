"""Integrated console command entry with contextual, non-executing guidance."""

from __future__ import annotations

import sys
import tkinter as tk

import customtkinter as ctk

from app.core.command_completion import (
    CommandCompletionContext,
    CommandCompletionService,
    CommandSuggestionResult,
)
from app.gui.customtkinter_compat import (
    ScopedEventBindings,
    ScopedScrollRouter,
    safe_focus,
    widget_exists,
)
from app.widgets.gothic_button import GothicButton
from app.widgets.gothic_frame import GothicFrame


class CommandSuggestionScroller(ctk.CTkFrame):
    """Bounded host-owned viewport with scoped wheel/touchpad routing."""

    def __init__(self, parent, theme):
        super().__init__(
            parent,
            height=190,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["gold_dark"],
            corner_radius=8,
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            background=theme["panel"],
            borderwidth=0,
            highlightthickness=0,
            yscrollincrement=1,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(3, 0), pady=3)
        self.scrollbar = ctk.CTkScrollbar(
            self,
            width=17,
            command=self.canvas.yview,
            fg_color=theme["panel"],
            button_color=theme["gold_dark"],
            button_hover_color=theme["red_hover"],
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 3), pady=3)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ctk.CTkFrame(
            self.canvas, fg_color=theme["panel"], corner_radius=0
        )
        self.content.grid_columnconfigure(0, weight=1)
        self.window_id = self.canvas.create_window(
            0, 0, window=self.content, anchor="nw"
        )
        self.router = ScopedScrollRouter(
            self, self.canvas, owner=parent, keyboard=False, scroll_units=42,
            visible=lambda: bool(self.winfo_ismapped()),
        )
        self.canvas.bind("<Configure>", self._canvas_configured, add="+")
        self.content.bind("<Configure>", self._sync_region, add="+")

    def _canvas_configured(self, event):
        self.canvas.itemconfigure(self.window_id, width=max(1, event.width - 2))
        self._sync_region()

    def _sync_region(self, _event=None):
        if widget_exists(self.canvas):
            self.canvas.configure(
                scrollregion=self.canvas.bbox("all") or (0, 0, 1, 1)
            )

    def ensure_visible(self, widget):
        self.router.ensure_visible(widget)

    def close(self):
        self.router.close()


class CommandBar(GothicFrame):
    REFRESH_DELAY_MS = 90
    PAGE_SIZE = 5

    def __init__(
        self,
        parent,
        execute_callback,
        *,
        theme=None,
        completion_service=None,
        context_provider=None,
        history=None,
    ):
        super().__init__(parent)
        self.execute_callback = execute_callback
        self.theme = theme or {
            "panel": "#131313", "panel_alt": "#1B1B1B", "border": "#2D2D2D",
            "gold": "#D6B55A", "gold_dark": "#8B6B1D", "red": "#6E0F0F",
            "red_hover": "#9B1717", "text": "#EFE2B0", "muted": "#9D9272",
            "terminal_bg": "#050505",
        }
        self.completion_service = completion_service or CommandCompletionService()
        self.context_provider = context_provider or CommandCompletionContext
        self.history = history
        self.result = CommandSuggestionResult()
        self.suggestion_buttons = []
        self.selected_index = -1
        self._refresh_id = None
        self._closed = False
        self.bindings = ScopedEventBindings()
        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter a supported command…",
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.entry.grid(
            row=0, column=0, sticky="ew", padx=(10, 5), pady=10,
        )

        self.run_button = GothicButton(
            self, text="Run", width=100, command=self.run,
        )
        self.run_button.grid(
            row=0, column=1, padx=(5, 10), pady=10,
        )

        self.suggestion_panel = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel_alt"],
            border_width=1,
            border_color=self.theme["gold_dark"],
            corner_radius=8,
        )
        self.suggestion_panel.grid_columnconfigure(0, weight=1)
        self.suggestion_header = ctk.CTkLabel(
            self.suggestion_panel,
            text="Command suggestions",
            text_color=self.theme["gold"],
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.suggestion_header.grid(
            row=0, column=0, sticky="ew", padx=(9, 4), pady=(5, 2)
        )
        self.suggestion_status = ctk.CTkLabel(
            self.suggestion_panel,
            text="",
            text_color=self.theme["muted"],
            font=("Segoe UI", 10),
            anchor="e",
        )
        self.suggestion_status.grid(
            row=0, column=1, sticky="e", padx=(4, 9), pady=(5, 2)
        )
        self.suggestion_scroller = CommandSuggestionScroller(
            self.suggestion_panel, self.theme
        )
        self.suggestion_scroller.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(1, 5)
        )
        self.suggestion_panel.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8)
        )
        self.suggestion_panel.grid_remove()

        self.session_prompt = ctk.CTkFrame(self, fg_color="transparent")
        self.session_prompt.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8),
        )
        self.session_prompt.grid_columnconfigure(0, weight=1)
        self.session_label = ctk.CTkLabel(
            self.session_prompt,
            text="This command opens an interactive session.",
            text_color=self.theme["gold"],
            anchor="w",
        )
        self.session_label.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.open_session_button = GothicButton(
            self.session_prompt, text="Open Dedicated Session", width=180,
        )
        self.open_session_button.grid(row=0, column=1, padx=4)
        self.cancel_session_button = GothicButton(
            self.session_prompt,
            text="Cancel",
            width=90,
            command=self.hide_session_prompt,
        )
        self.cancel_session_button.grid(row=0, column=2, padx=4)
        self.session_prompt.grid_remove()
        self._bind_entry()

    @property
    def suggestions_open(self):
        return bool(
            self.result.suggestions
            and widget_exists(self.suggestion_panel)
            and self.suggestion_panel.winfo_ismapped()
        )

    @property
    def callback_count(self):
        return int(self._refresh_id is not None)

    @property
    def binding_count(self):
        return self.bindings.count + self.suggestion_scroller.router.count

    def _bind_entry(self):
        target = getattr(self.entry, "_entry", self.entry)
        for sequence, callback in (
            ("<Return>", self.run),
            ("<KeyRelease>", self._key_released),
            ("<Tab>", self._tab),
            ("<ISO_Left_Tab>", self._shift_tab),
            ("<Shift-Tab>", self._shift_tab),
            ("<Up>", lambda event: self._vertical(event, -1)),
            ("<Down>", lambda event: self._vertical(event, 1)),
            ("<Prior>", lambda event: self._page(event, -self.PAGE_SIZE)),
            ("<Next>", lambda event: self._page(event, self.PAGE_SIZE)),
            ("<Escape>", self._escape),
            ("<Control-space>", self._manual),
            ("<Right>", self._right),
        ):
            self.bindings.bind(target, sequence, callback)
        for sequence in self._select_all_sequences():
            self.bindings.bind(target, sequence, self._select_all_command)

    @staticmethod
    def _select_all_sequences(platform=None):
        sequences = ["<Control-a>", "<Control-A>"]
        if (platform or sys.platform) == "darwin":
            sequences.extend(("<Command-a>", "<Command-A>"))
        return tuple(sequences)

    def _select_all_command(self, _event=None):
        """Select the full command and leave its insertion caret at the end."""
        target = getattr(self.entry, "_entry", self.entry)
        safe_focus(target)
        target.selection_range(0, "end")
        target.icursor("end")
        return "break"

    def _key_released(self, event):
        if getattr(event, "keysym", "") in {
            "Return", "Tab", "ISO_Left_Tab", "Up", "Down", "Prior", "Next",
            "Escape", "Control_L", "Control_R", "Shift_L", "Shift_R", "Right",
        }:
            return None
        if self.history is not None:
            self.history.reset_navigation()
        self._schedule_refresh()
        return None

    def _schedule_refresh(self):
        self._cancel_refresh()
        if not self._closed:
            self._refresh_id = self.after(self.REFRESH_DELAY_MS, self._refresh)

    def _cancel_refresh(self):
        if self._refresh_id is not None:
            try:
                self.after_cancel(self._refresh_id)
            except tk.TclError:
                pass
            self._refresh_id = None

    def _refresh(self, manual=False):
        self._cancel_refresh()
        if self._closed or not widget_exists(self.entry):
            return "break"
        self.result = self.completion_service.suggest(
            self.entry.get(),
            self.context_provider(),
            cursor=self.entry.index("insert"),
            manual=manual,
        )
        if not self.result.suggestions:
            self.hide_suggestions()
            return "break"
        self._render_suggestions()
        return "break"

    def _render_suggestions(self):
        scale = max(1.0, float(self.suggestion_scroller._get_widget_scaling()))
        self.suggestion_scroller.configure(
            height=max(80, round(190 / (scale * scale)))
        )
        for child in self.suggestion_scroller.content.winfo_children():
            child.destroy()
        self.suggestion_buttons.clear()
        self.selected_index = 0
        self.suggestion_header.configure(text=self.result.heading)
        visible = len(self.result.suggestions)
        self.suggestion_status.configure(
            text=(
                f"{visible}/{self.result.total_count} · {self.result.context_note}"
                if self.result.total_count > visible
                else f"{visible} · {self.result.context_note}"
            )
        )
        for index, suggestion in enumerate(self.result.suggestions):
            badges = [
                "Related" if suggestion.related else "",
                "Interactive session" if suggestion.opens_session else "One-shot",
                "Device" if suggestion.requires_device else "",
                "Target" if suggestion.uses_target else "",
                "State-changing" if suggestion.impact == "State-changing" else "",
            ]
            badge_text = " · ".join(value for value in badges if value)
            button = ctk.CTkButton(
                self.suggestion_scroller.content,
                text=(
                    f"{suggestion.display_syntax}\n"
                    f"{suggestion.description}\n"
                    f"{suggestion.family} / {suggestion.category}"
                    f"{'  ·  ' + badge_text if badge_text else ''}"
                ),
                command=lambda value=index: self.accept_index(value),
                height=64,
                anchor="w",
                fg_color=self.theme["panel_alt"],
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"],
                border_width=1,
                border_color=self.theme["border"],
                font=("Segoe UI", 11),
            )
            button.grid(row=index, column=0, sticky="ew", padx=4, pady=2)
            button.bind(
                "<Enter>", lambda _event, value=index: self.select_index(value),
                add="+",
            )
            self.suggestion_buttons.append(button)
        self.suggestion_panel.grid()
        self._paint_selection()
        self.suggestion_scroller._sync_region()

    def select_index(self, index):
        if not self.result.suggestions:
            return "break"
        self.selected_index = min(
            max(0, int(index)), len(self.result.suggestions) - 1
        )
        self._paint_selection()
        return "break"

    def _paint_selection(self):
        for index, button in enumerate(self.suggestion_buttons):
            selected = index == self.selected_index
            button.configure(
                fg_color=self.theme["red"] if selected else self.theme["panel_alt"],
                border_color=self.theme["gold"] if selected else self.theme["border"],
            )
        if 0 <= self.selected_index < len(self.suggestion_buttons):
            self.suggestion_scroller.ensure_visible(
                self.suggestion_buttons[self.selected_index]
            )

    def accept_index(self, index):
        if not self.result.suggestions:
            return "break"
        self.select_index(index)
        suggestion = self.result.suggestions[self.selected_index]
        value, cursor = suggestion.apply(self.entry.get())
        self._set_entry(value, cursor)
        self.hide_suggestions()
        safe_focus(self.entry)
        return "break"

    def _set_entry(self, value, cursor=None):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.entry.icursor(len(value) if cursor is None else cursor)

    def handoff_character(self, character):
        """Insert one transcript-misclick character without executing anything."""
        if self._closed or len(character) != 1 or not character.isprintable():
            return False
        inner = getattr(self.entry, "_entry", self.entry)
        safe_focus(inner)
        try:
            if inner.selection_present():
                start = inner.index("sel.first")
                end = inner.index("sel.last")
                self.entry.delete(start, end)
        except tk.TclError:
            pass
        cursor = self.entry.index("insert")
        self.entry.insert(cursor, character)
        self.entry.icursor(cursor + 1)
        if self.history is not None:
            self.history.reset_navigation()
        self._schedule_refresh()
        return True

    def _tab(self, _event=None):
        if not self.suggestions_open:
            self._refresh(manual=True)
        if not self.result.suggestions:
            return "break"
        if len(self.result.suggestions) == 1:
            return self.accept_index(0)
        if self.selected_index >= 0:
            return self.accept_index(self.selected_index)
        prefix = self.result.common_prefix
        current = self.entry.get()
        if prefix and len(prefix) > len(current.strip()):
            start = len(current) - len(current.lstrip())
            self._set_entry(current[:start] + prefix, start + len(prefix))
            self._refresh(manual=True)
        return "break"

    def _shift_tab(self, _event=None):
        if not self.suggestions_open:
            return None
        return self.select_index(
            self.selected_index - 1
            if self.selected_index > 0 else len(self.result.suggestions) - 1
        )

    def _vertical(self, _event, amount):
        if self.suggestions_open:
            return self.select_index(self.selected_index + amount)
        if self.history is None:
            return None
        value = self.history.previous() if amount < 0 else self.history.next()
        self._set_entry(value)
        return "break"

    def _page(self, _event, amount):
        if not self.suggestions_open:
            return None
        return self.select_index(self.selected_index + amount)

    def _escape(self, _event=None):
        if self.suggestions_open:
            self.hide_suggestions()
            return "break"
        return None

    def _manual(self, _event=None):
        self._cancel_refresh()
        self._refresh(manual=True)
        return "break"

    def _right(self, _event=None):
        if not self.suggestions_open or self.entry.index("insert") != len(self.entry.get()):
            return None
        inner = getattr(self.entry, "_entry", self.entry)
        try:
            if inner.selection_present():
                return None
        except tk.TclError:
            return None
        prefix = self.result.common_prefix
        current = self.entry.get()
        leading = len(current) - len(current.lstrip())
        if prefix and len(prefix) > len(current.strip()):
            self._set_entry(current[:leading] + prefix, leading + len(prefix))
            self._refresh(manual=True)
            return "break"
        return None

    def run(self, event=None):
        self._cancel_refresh()
        self.hide_suggestions()
        command = self.entry.get().strip()
        if command:
            self.execute_callback(command)
            self.entry.delete(0, "end")
        return "break" if event is not None else None

    def hide_suggestions(self):
        self._cancel_refresh()
        self.suggestion_panel.grid_remove()
        self.result = CommandSuggestionResult()
        self.selected_index = -1

    def show_session_prompt(self, route, open_callback):
        self.hide_suggestions()
        self.session_label.configure(
            text=f"This command opens an interactive session.\n{route.reason}"
        )
        self.open_session_button.configure(
            command=lambda: self._open_session(route, open_callback)
        )
        self.session_prompt.grid()

    def _open_session(self, route, callback):
        self.session_prompt.grid_remove()
        callback(route)

    def hide_session_prompt(self):
        self.session_prompt.grid_remove()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._cancel_refresh()
        self.hide_suggestions()
        self.bindings.close()
        self.suggestion_scroller.close()

    def destroy(self):
        self.close()
        super().destroy()
