"""Virtualized, bounded timeline for immutable Logcat events."""

from __future__ import annotations

import math
import tkinter as tk

import customtkinter as ctk

from app.gui.customtkinter_compat import (
    ScopedEventBindings,
    ScopedScrollRouter,
    safe_focus,
    widget_exists,
)


class LogcatEventTimeline(ctk.CTkFrame):
    """Render only visible fixed-height cards while retaining at most 1,000 models."""

    CARD_HEIGHT = 132
    CARD_GAP = 8
    HORIZONTAL_PADDING = 8

    def __init__(self, parent, theme, *, details_callback, transcript_callback):
        super().__init__(
            parent,
            fg_color=theme["terminal_bg"],
            border_width=1,
            border_color=theme["border"],
        )
        self.theme = theme
        self.details_callback = details_callback
        self.transcript_callback = transcript_callback
        self.events = ()
        self.selected_event_id = ""
        self._closed = False
        self._rendered_range = (-1, -1)
        self._hit_regions = []
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            bg=theme["terminal_bg"],
            highlightthickness=0,
            bd=0,
            takefocus=True,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ctk.CTkScrollbar(
            self,
            command=self._scroll_command,
            fg_color=theme["panel"],
            button_color=theme["gold_dark"],
            button_hover_color=theme["red_hover"],
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self._scroll_changed)
        self.bindings = ScopedEventBindings()
        self.bindings.bind(self.canvas, "<Configure>", self._configured)
        self.bindings.bind(self.canvas, "<Button-1>", self._clicked)
        self.scroll_router = ScopedScrollRouter(
            self,
            self.canvas,
            owner=self.winfo_toplevel(),
            scroll_units=3,
            visible=lambda: bool(self.winfo_ismapped()),
        )
        self._refresh_scrollregion()

    @property
    def binding_count(self):
        return self.bindings.count + self.scroll_router.count

    def _scroll_command(self, *args):
        if self._closed or not widget_exists(self.canvas):
            return
        self.canvas.yview(*args)
        self._render_visible()

    def _scroll_changed(self, first, last):
        if self._closed:
            return
        self.scrollbar.set(first, last)
        self._render_visible()

    def _configured(self, _event=None):
        self._rendered_range = (-1, -1)
        self._render_visible()

    def _refresh_scrollregion(self):
        extent = max(
            1,
            len(self.events) * (self.CARD_HEIGHT + self.CARD_GAP)
            + self.CARD_GAP,
        )
        self.canvas.configure(scrollregion=(0, 0, 1, extent))
        self._rendered_range = (-1, -1)
        self._render_visible()

    def set_events(self, events):
        selected = self.selected_event_id
        self.events = tuple(events)[:1_000]
        if selected and not any(value.event_id == selected for value in self.events):
            self.selected_event_id = ""
        self._refresh_scrollregion()

    def select_event(self, event_id):
        if event_id == self.selected_event_id:
            return
        self.selected_event_id = str(event_id or "")
        self._rendered_range = (-1, -1)
        self._render_visible()

    def scroll_to_event(self, event_id):
        index = next(
            (
                index for index, event in enumerate(self.events)
                if event.event_id == event_id
            ),
            None,
        )
        if index is None:
            return False
        extent = max(1, len(self.events) * (self.CARD_HEIGHT + self.CARD_GAP))
        self.canvas.yview_moveto(
            min(1.0, index * (self.CARD_HEIGHT + self.CARD_GAP) / extent)
        )
        self.select_event(event_id)
        return True

    def _visible_range(self):
        if not self.events:
            return 0, 0
        top = max(0.0, self.canvas.canvasy(0))
        height = max(1, self.canvas.winfo_height())
        stride = self.CARD_HEIGHT + self.CARD_GAP
        first = max(0, int(top // stride) - 1)
        last = min(len(self.events), int(math.ceil((top + height) / stride)) + 1)
        return first, last

    @staticmethod
    def _compact(value, maximum):
        text = " ".join(str(value or "").split())
        return text if len(text) <= maximum else text[: maximum - 1] + "…"

    def _render_visible(self):
        if self._closed or not widget_exists(self.canvas):
            return
        first, last = self._visible_range()
        if (first, last) == self._rendered_range:
            return
        self._rendered_range = (first, last)
        self.canvas.delete("card")
        self._hit_regions.clear()
        width = max(320, self.canvas.winfo_width())
        left = self.HORIZONTAL_PADDING
        right = width - self.HORIZONTAL_PADDING
        stride = self.CARD_HEIGHT + self.CARD_GAP
        for index in range(first, last):
            event = self.events[index]
            top = self.CARD_GAP + index * stride
            bottom = top + self.CARD_HEIGHT
            selected = event.event_id == self.selected_event_id
            self.canvas.create_rectangle(
                left,
                top,
                right,
                bottom,
                fill=self.theme["panel_alt"] if selected else self.theme["panel"],
                outline=self.theme["gold"] if selected else self.theme["border"],
                width=2 if selected else 1,
                tags=("card",),
            )
            header = (
                f"{event.kind.label} · {event.severity.label} · "
                f"{event.confidence.label} · ×{event.occurrence_count}"
            )
            identity = event.process or event.package or "Process unavailable"
            if event.pid is not None:
                identity += f" · PID {event.pid}"
            timestamps = event.first_timestamp_text or "Timestamp unavailable"
            if event.last_timestamp_text and event.last_timestamp_text != timestamps:
                timestamps += f" → {event.last_timestamp_text}"
            self.canvas.create_text(
                left + 10,
                top + 10,
                text=self._compact(header, 110),
                fill=self.theme["gold"],
                anchor="nw",
                font=("Segoe UI", 9, "bold"),
                tags=("card",),
            )
            self.canvas.create_text(
                left + 10,
                top + 34,
                text=self._compact(event.title, 120),
                fill=self.theme["text"],
                anchor="nw",
                font=("Segoe UI", 11, "bold"),
                tags=("card",),
            )
            self.canvas.create_text(
                left + 10,
                top + 58,
                text=self._compact(f"{identity} · {timestamps}", 135),
                fill=self.theme["muted"],
                anchor="nw",
                font=("Segoe UI", 9),
                tags=("card",),
            )
            self.canvas.create_text(
                left + 10,
                top + 80,
                text=self._compact(event.summary, 125),
                fill=self.theme["terminal_text"],
                anchor="nw",
                font=("Consolas", 9),
                tags=("card",),
            )
            action_top = bottom - 29
            transcript_left = max(left + 130, right - 142)
            details_left = max(left + 10, transcript_left - 120)
            actions = (
                (
                    details_left,
                    transcript_left - 8,
                    "View Details",
                    self.details_callback,
                ),
                (
                    transcript_left,
                    right - 8,
                    "Show in Transcript",
                    self.transcript_callback,
                ),
            )
            for action_left, action_right, label, callback in actions:
                self.canvas.create_rectangle(
                    action_left,
                    action_top,
                    action_right,
                    bottom - 6,
                    fill=self.theme["red"],
                    outline=self.theme["gold_dark"],
                    tags=("card",),
                )
                self.canvas.create_text(
                    (action_left + action_right) / 2,
                    action_top + 11,
                    text=label,
                    fill=self.theme["text"],
                    font=("Segoe UI", 8, "bold"),
                    tags=("card",),
                )
                self._hit_regions.append(
                    (
                        action_left,
                        action_top,
                        action_right,
                        bottom - 6,
                        event,
                        callback,
                    )
                )

    def _clicked(self, event):
        if self._closed:
            return None
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        for left, top, right, bottom, value, callback in self._hit_regions:
            if left <= x <= right and top <= y <= bottom:
                self.select_event(value.event_id)
                callback(value)
                safe_focus(self.canvas)
                return "break"
        stride = self.CARD_HEIGHT + self.CARD_GAP
        index = int(max(0, y - self.CARD_GAP) // stride)
        if 0 <= index < len(self.events):
            value = self.events[index]
            self.select_event(value.event_id)
            self.details_callback(value)
            safe_focus(self.canvas)
            return "break"
        return None

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.scroll_router.close()
        self.bindings.close()
        self._hit_regions.clear()
        self.events = ()

    def destroy(self):
        self.close()
        super().destroy()
