"""Measured, wrapping CustomTkinter action rows."""

from __future__ import annotations

import customtkinter as ctk

from app.core.responsive_layout import estimated_button_width


class ResponsiveActionGrid(ctk.CTkFrame):
    """Preserve button identity and traversal order while wrapping by width."""

    def __init__(
        self,
        parent,
        theme,
        items,
        *,
        minimum_width=118,
        button_height=32,
        gap=6,
    ):
        super().__init__(parent, fg_color="transparent")
        self.theme = theme
        self.minimum_width = minimum_width
        self.button_height = button_height
        self.gap = gap
        self.buttons = []
        self._layout_pending = False
        self._last_layout = None
        self._configured_columns = 0
        for text, command in items:
            button = ctk.CTkButton(
                self,
                text=text,
                command=command,
                width=estimated_button_width(text, minimum_width),
                height=button_height,
                fg_color=theme["red"],
                hover_color=theme["red_hover"],
                text_color=theme["text"],
                border_width=1,
                border_color=theme["gold_dark"],
            )
            self.buttons.append(button)
        self.bind("<Configure>", self._schedule_layout, add="+")
        self.after_idle(self._layout)

    def _schedule_layout(self, _event=None):
        if self._layout_pending:
            return
        self._layout_pending = True
        self.after_idle(self._layout)

    def _layout(self):
        self._layout_pending = False
        if not self.winfo_exists() or not self.buttons:
            return
        available = max(1, self.winfo_width())
        widths = [
            estimated_button_width(button.cget("text"), self.minimum_width)
            for button in self.buttons
        ]
        largest = max(widths)
        columns = max(1, min(len(self.buttons), available // (largest + self.gap)))
        signature = (columns, tuple(widths))
        if signature == self._last_layout:
            return
        self._last_layout = signature
        for column in range(max(columns, self._configured_columns)):
            self.grid_columnconfigure(column, weight=1 if column < columns else 0)
        self._configured_columns = columns
        for index, button in enumerate(self.buttons):
            button.grid(
                row=index // columns,
                column=index % columns,
                sticky="ew",
                padx=self.gap // 2,
                pady=self.gap // 2,
            )

    def set_active(self, text):
        for button in self.buttons:
            active = button.cget("text") == text
            button.configure(
                fg_color=self.theme["red"] if active else self.theme["panel_alt"],
                border_color=(
                    self.theme["gold"] if active else self.theme["gold_dark"]
                ),
            )


class HorizontalNavigationStrip(ctk.CTkScrollableFrame):
    """Single-row, safely scrollable navigation with untruncated labels."""

    def __init__(self, parent, theme, items):
        super().__init__(
            parent,
            orientation="horizontal",
            height=48,
            fg_color=theme["panel_alt"],
            scrollbar_button_color=theme["gold_dark"],
            scrollbar_button_hover_color=theme["red_hover"],
        )
        self.theme = theme
        self.buttons = []
        for text, command in items:
            button = ctk.CTkButton(
                self,
                text=text,
                command=command,
                width=estimated_button_width(text, 88),
                height=30,
                fg_color=theme["panel_alt"],
                hover_color=theme["red_hover"],
                text_color=theme["text"],
                border_width=1,
                border_color=theme["gold_dark"],
            )
            button.pack(side="left", padx=3, pady=(2, 5))
            self.buttons.append(button)

    def set_active(self, text):
        for button in self.buttons:
            active = button.cget("text") == text
            button.configure(
                fg_color=self.theme["red"] if active else self.theme["panel_alt"],
                border_color=(
                    self.theme["gold"] if active else self.theme["gold_dark"]
                ),
            )
