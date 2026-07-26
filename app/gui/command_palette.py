"""Lazy, keyboard-first Universal Command Palette."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.gui.customtkinter_compat import (
    PendingCallbackOwner,
    safe_focus,
    wheel_scroll_units,
    widget_exists,
)


class PaletteResultScroller(ctk.CTkFrame):
    """A bounded vertical result viewport with scoped wheel handling."""

    def __init__(self, parent, theme):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=8,
        )
        self.theme = theme
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            background=theme["panel"],
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=theme["border"],
            highlightcolor=theme["gold"],
            takefocus=True,
            yscrollincrement=1,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ctk.CTkScrollbar(
            self,
            orientation="vertical",
            width=17,
            command=self.canvas.yview,
            fg_color=theme["panel"],
            button_color=theme["gold_dark"],
            button_hover_color=theme["red_hover"],
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(5, 3), pady=3)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ctk.CTkFrame(
            self.canvas, fg_color=theme["panel"], corner_radius=0
        )
        self.content.grid_columnconfigure(0, weight=1)
        self.window_id = self.canvas.create_window(
            0, 0, window=self.content, anchor="nw"
        )
        self._binding_ids = []
        self.canvas.bind("<Configure>", self._canvas_configured, add="+")
        self.content.bind("<Configure>", self._content_configured, add="+")
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            binding_id = parent.bind(sequence, self._wheel, add="+")
            if binding_id:
                self._binding_ids.append((sequence, binding_id))

    def _inside(self, widget):
        if not isinstance(widget, tk.Misc):
            return False
        try:
            while widget is not None:
                if widget in {self, self.canvas, self.content}:
                    return True
                widget = getattr(widget, "master", None)
        except (AttributeError, tk.TclError):
            return False
        return False

    def _wheel(self, event):
        if not self._inside(getattr(event, "widget", None)):
            return None
        units = wheel_scroll_units(event, lines=42)
        if not units:
            return None
        self.canvas.yview_scroll(units, "units")
        return "break"

    def _canvas_configured(self, event):
        self.canvas.itemconfigure(self.window_id, width=max(1, event.width - 2))
        self._sync_region()

    def _content_configured(self, _event=None):
        self._sync_region()

    def _sync_region(self):
        if not widget_exists(self.canvas):
            return
        self.canvas.configure(scrollregion=self.canvas.bbox("all") or (0, 0, 1, 1))

    def ensure_visible(self, widget):
        if not widget_exists(widget):
            return
        self.update_idletasks()
        try:
            top = widget.winfo_rooty() - self.content.winfo_rooty()
            bottom = top + widget.winfo_height()
            view_top = self.canvas.canvasy(0)
            view_height = max(1, self.canvas.winfo_height())
            extent = max(1, self.content.winfo_reqheight())
            target = view_top
            if top < view_top:
                target = top
            elif bottom > view_top + view_height:
                target = bottom - view_height
            maximum = max(0, extent - view_height)
            target = min(max(0, target), maximum)
            self.canvas.yview_moveto(target / extent)
        except tk.TclError:
            return

    def close(self):
        parent = self.master
        if widget_exists(parent):
            for sequence, binding_id in self._binding_ids:
                try:
                    parent.unbind(sequence, binding_id)
                except tk.TclError:
                    pass
        self._binding_ids.clear()


class CommandPaletteWindow(ctk.CTkToplevel):
    """Non-modal singleton view over a host-owned command registry."""

    RESULT_LIMIT = 16
    PAGE_SIZE = 6

    def __init__(
        self,
        parent,
        theme,
        registry,
        command_provider,
        *,
        subscriptions=(),
        mode_provider=lambda: "guided",
        on_close=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.registry = registry
        self.command_provider = command_provider
        self.mode_provider = mode_provider
        self.on_close = on_close
        self.matches = ()
        self.result_buttons = []
        self.selected_index = 0
        self._closed = False
        self._subscriptions = []
        self.callbacks = PendingCallbackOwner(self)
        self.title(f"{METADATA.application_name} — Universal Command Palette")
        self.configure(fg_color=theme["bg"])
        self.minsize(720, 500)
        self.geometry(self._center(820, 560))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build_header()
        self._build_results()
        self._build_footer()
        for sequence, callback in (
            ("<Escape>", lambda _event: self.close()),
            ("<Up>", lambda _event: self.move_selection(-1)),
            ("<Down>", lambda _event: self.move_selection(1)),
            ("<Prior>", lambda _event: self.move_selection(-self.PAGE_SIZE)),
            ("<Next>", lambda _event: self.move_selection(self.PAGE_SIZE)),
            ("<Home>", lambda _event: self.select_index(0)),
            ("<End>", lambda _event: self.select_index(len(self.matches) - 1)),
            ("<Return>", lambda _event: self.activate_selected()),
        ):
            self.bind(sequence, callback, add="+")
        for subscribe in subscriptions:
            cancellation = subscribe(self.request_refresh)
            if cancellation is not None:
                self._subscriptions.append(cancellation)
        self.refresh()
        self.after_idle(self.focus_search)

    def _center(self, width, height):
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(width, screen_width)
        height = min(height, screen_height)
        parent = self.master
        if widget_exists(parent):
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        else:
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
        x = min(max(0, x), max(0, screen_width - width))
        y = min(max(0, y), max(0, screen_height - height))
        return f"{width}x{height}+{x}+{y}"

    def _build_header(self):
        header = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 5))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            header,
            text="⌘ UNIVERSAL COMMAND PALETTE",
            text_color=self.theme["gold"],
            font=("Times New Roman", 24, "bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 2))
        self.mode_label = ctk.CTkLabel(
            header, text="", text_color=self.theme["muted"], anchor="e"
        )
        self.mode_label.grid(row=0, column=1, padx=10)
        self.search = ctk.CTkEntry(
            header,
            placeholder_text="Search workspaces, tools, add-ons, and help…",
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
            height=38,
        )
        self.search.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(3, 9)
        )
        self.search.bind("<KeyRelease>", self._query_changed, add="+")
        self.state_label = ctk.CTkLabel(
            self, text="", text_color=self.theme["gold"], anchor="w"
        )
        self.state_label.grid(row=1, column=0, sticky="ew", padx=17, pady=(2, 3))

    def _build_results(self):
        self.result_area = PaletteResultScroller(self, self.theme)
        self.result_area.grid(
            row=2, column=0, sticky="nsew", padx=14, pady=(2, 5)
        )

    def _build_footer(self):
        self.footer = ctk.CTkLabel(
            self,
            text="↑/↓ Navigate   Enter Open   Esc Close",
            text_color=self.theme["muted"],
            anchor="center",
        )
        self.footer.grid(row=3, column=0, sticky="ew", padx=14, pady=(3, 12))

    def _query_changed(self, event):
        if getattr(event, "keysym", "") not in {
            "Up", "Down", "Prior", "Next", "Home", "End", "Return", "Escape"
        }:
            self.refresh()

    def request_refresh(self, *_args):
        if self._closed:
            return
        self.callbacks.schedule_idle(self.refresh)

    def refresh(self):
        if self._closed or not widget_exists(self):
            return
        selected_id = (
            self.matches[self.selected_index].command.command_id
            if self.matches and self.selected_index < len(self.matches) else ""
        )
        self.registry.replace(self.command_provider())
        self.matches = self.registry.search(
            self.search.get(), limit=self.RESULT_LIMIT
        )
        for child in self.result_area.content.winfo_children():
            child.destroy()
        self.result_buttons.clear()
        row = 0
        last_category = None
        for index, match in enumerate(self.matches):
            command = match.command
            if command.category != last_category:
                ctk.CTkLabel(
                    self.result_area.content,
                    text=command.category.upper(),
                    text_color=self.theme["gold"],
                    font=("Segoe UI", 10, "bold"),
                    anchor="w",
                ).grid(row=row, column=0, sticky="ew", padx=10, pady=(8, 2))
                row += 1
                last_category = command.category
            context = (
                f"\n{command.technical_context}"
                if self.mode_provider() == "advanced"
                and command.technical_context else ""
            )
            availability = (
                f"\n{command.unavailable_reason}"
                if command.unavailable_reason else ""
            )
            hint = f"    {command.keyboard_hint}" if command.keyboard_hint else ""
            button = ctk.CTkButton(
                self.result_area.content,
                text=(
                    f"{command.title}{hint}\n"
                    f"{command.description}{context}{availability}"
                ),
                command=lambda value=index: self.activate_index(value),
                anchor="w",
                height=68,
                fg_color=self.theme["panel_alt"],
                hover_color=self.theme["red_hover"],
                text_color=(
                    self.theme["text"]
                    if command.available else self.theme["muted"]
                ),
                border_width=1,
                border_color=self.theme["border"],
            )
            button.grid(row=row, column=0, sticky="ew", padx=7, pady=3)
            tk.Frame.configure(button, takefocus=True)
            button.bind(
                "<FocusIn>",
                lambda _event, value=index: self.select_index(value),
                add="+",
            )
            self.result_buttons.append(button)
            row += 1
        if not self.matches:
            ctk.CTkLabel(
                self.result_area.content,
                text="No matching safe navigation destination.",
                text_color=self.theme["muted"],
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=24)
        matching_index = next(
            (
                index for index, match in enumerate(self.matches)
                if match.command.command_id == selected_id
            ),
            0,
        )
        self.selected_index = matching_index
        self.mode_label.configure(
            text=f"{self.mode_provider().title()} mode"
        )
        self.state_label.configure(
            text=(
                f"{len(self.matches)} result"
                f"{'' if len(self.matches) == 1 else 's'} · navigation only"
            )
        )
        self._paint_selection()
        self.result_area._sync_region()

    def _paint_selection(self):
        for index, button in enumerate(self.result_buttons):
            button.configure(
                fg_color=(
                    self.theme["red"]
                    if index == self.selected_index else self.theme["panel_alt"]
                ),
                border_color=(
                    self.theme["gold"]
                    if index == self.selected_index else self.theme["border"]
                ),
            )
        if self.result_buttons:
            self.result_area.ensure_visible(
                self.result_buttons[self.selected_index]
            )

    def select_index(self, index):
        if not self.matches:
            return "break"
        self.selected_index = min(max(0, int(index)), len(self.matches) - 1)
        self._paint_selection()
        return "break"

    def move_selection(self, amount):
        return self.select_index(self.selected_index + int(amount))

    def activate_index(self, index):
        self.select_index(index)
        return self.activate_selected()

    def activate_selected(self):
        if not self.matches:
            return "break"
        command = self.matches[self.selected_index].command
        if not command.available:
            self.state_label.configure(
                text=command.unavailable_reason or "This destination is unavailable."
            )
            return "break"
        query = self.search.get().strip()
        command_id = command.command_id
        self.close()
        self.registry.invoke(command_id, query)
        return "break"

    def focus_search(self):
        if not self._closed:
            self.deiconify()
            self.lift()
            safe_focus(self.search)
        return self

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.callbacks.cancel_all()
        for cancellation in tuple(self._subscriptions):
            if hasattr(cancellation, "cancel"):
                cancellation.cancel()
            elif callable(cancellation):
                cancellation()
        self._subscriptions.clear()
        self.result_area.close()
        if self.on_close:
            self.on_close()
        self.destroy()
