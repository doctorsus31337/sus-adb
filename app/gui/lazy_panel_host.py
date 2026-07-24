"""GUI-thread-only lazy host for heavyweight CustomTkinter panels."""

from __future__ import annotations

import threading

import customtkinter as ctk


class LazyPanelHost(ctk.CTkFrame):
    def __init__(self, parent, theme, title, factory, on_ready=None):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme = theme
        self.title = title
        self.factory = factory
        self.on_ready = on_ready
        self.panel = None
        self.error = ""
        self.state = "pending"
        self.shutdown_started = False
        self.construction_thread_id = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.placeholder = ctk.CTkFrame(
            self, fg_color=theme["panel"], border_width=1, border_color=theme["border"]
        )
        self.placeholder.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.placeholder.grid_columnconfigure(0, weight=1)
        self.placeholder.grid_rowconfigure(0, weight=1)
        self.message = ctk.CTkLabel(
            self.placeholder,
            text=f"{title}\nConstructed on first explicit access.",
            text_color=theme["muted"],
            font=theme["header_font"],
            justify="center",
            wraplength=720,
        )
        self.message.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.retry = ctk.CTkButton(
            self.placeholder,
            text="Retry",
            command=self.ensure,
            fg_color=theme["red"],
            hover_color=theme["red_hover"],
            text_color=theme["text"],
        )

    def ensure(self):
        if self.panel is not None or self.shutdown_started:
            return self.panel
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Tk panels must be constructed on the GUI thread.")
        self.state = "loading"
        self.error = ""
        self.retry.grid_forget()
        self.message.configure(text=f"Loading {self.title}…", text_color=self.theme["gold"])
        self.update_idletasks()
        try:
            self.construction_thread_id = threading.get_ident()
            panel = self.factory(self)
            panel.grid(row=0, column=0, sticky="nsew")
            self.panel = panel
            self.placeholder.grid_remove()
            self.state = "ready"
            if self.on_ready:
                self.on_ready(panel)
            return panel
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"[:320]
            self.state = "failed"
            self.message.configure(
                text=f"{self.title} could not be constructed.\n{self.error}",
                text_color=self.theme["error"],
            )
            self.retry.grid(row=1, column=0, pady=(0, 18))
            return None

    def shutdown(self):
        self.shutdown_started = True
