"""Responsive typographic Gothic splash owned by the main Tk root."""

from __future__ import annotations

import customtkinter as ctk

from app.core.app_metadata import METADATA


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent, theme, tip_catalog, *, width=720, height=430):
        super().__init__(parent)
        self.theme = theme
        self.tip_catalog = tip_catalog
        self._tip_index = 0
        self.overrideredirect(True)
        self.configure(fg_color=theme["bg"])
        self.geometry(self._clamped_geometry(width, height))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        frame = ctk.CTkFrame(
            self,
            fg_color=theme["panel"],
            border_width=2,
            border_color=theme["gold_dark"],
            corner_radius=16,
        )
        frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(4, weight=1)
        self.brand_label = ctk.CTkLabel(
            frame,
            text=f"⚔ {METADATA.display_mark} ⚔",
            text_color=theme["gold"],
            font=("Times New Roman", 42, "bold"),
        )
        self.brand_label.grid(row=0, column=0, sticky="ew", padx=24, pady=(42, 4))
        ctk.CTkLabel(
            frame,
            text=METADATA.descriptor,
            text_color=theme["text"],
            font=("Times New Roman", 19, "italic"),
        ).grid(row=1, column=0, sticky="ew", padx=24)
        ctk.CTkLabel(
            frame,
            text="Authorized Android Analysis · Recovery · Instrumentation",
            text_color=theme["muted"],
            font=("Segoe UI", 12),
        ).grid(row=2, column=0, sticky="ew", padx=24, pady=(5, 24))
        self.stage_label = ctk.CTkLabel(
            frame, text="Preparing local bootstrap…", text_color=theme["gold"], anchor="w"
        )
        self.stage_label.grid(row=3, column=0, sticky="ew", padx=42, pady=(0, 7))
        self.progress = ctk.CTkProgressBar(
            frame,
            mode="determinate",
            progress_color=theme["red"],
            fg_color=theme["panel_alt"],
            border_color=theme["gold_dark"],
            border_width=1,
        )
        self.progress.grid(row=4, column=0, sticky="ew", padx=42, pady=(0, 18))
        self.progress.set(0)
        self.tip_label = ctk.CTkLabel(
            frame,
            text=self.tip_catalog.select(0),
            text_color=theme["muted"],
            justify="center",
            wraplength=610,
        )
        self.tip_label.grid(row=5, column=0, sticky="ew", padx=42, pady=(0, 34))
        self.failure_actions = ctk.CTkFrame(frame, fg_color="transparent")
        self.failure_actions.grid(row=6, column=0, sticky="e", padx=42, pady=(0, 24))
        self.copy_button = ctk.CTkButton(
            self.failure_actions, text="Copy Sanitized Diagnostics", command=self._copy_failure,
            fg_color=theme["panel_alt"], hover_color=theme["gold_dark"], text_color=theme["text"],
        )
        self.copy_button.pack(side="left", padx=5)
        self.close_button = ctk.CTkButton(
            self.failure_actions, text="Close", command=getattr(parent,"shutdown",parent.destroy),
            fg_color=theme["red"], hover_color=theme["red_hover"], text_color=theme["text"],
        )
        self.close_button.pack(side="left", padx=5)
        self.failure_actions.grid_remove()
        self.failure_diagnostics = ""

    def _clamped_geometry(self, width, height):
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = max(600, min(int(width), screen_w))
        height = max(360, min(int(height), screen_h))
        return f"{width}x{height}+{max(0, (screen_w-width)//2)}+{max(0, (screen_h-height)//2)}"

    def paint_now(self):
        self.deiconify()
        self.lift()
        self.update_idletasks()
        self.update()

    def update_stage(self, completed, total, text, *, rotate_tip=False):
        if not self.winfo_exists():
            return
        self.stage_label.configure(text=str(text)[:160], text_color=self.theme["gold"])
        self.progress.set(max(0.0, min(1.0, float(completed) / max(1, int(total)))))
        if rotate_tip and len(self.tip_catalog.tips) > 1:
            self._tip_index += 1
            self.tip_label.configure(text=self.tip_catalog.select(self._tip_index))
        self.update_idletasks()
        self.update()

    def show_failure(self, message, diagnostics=""):
        self.failure_diagnostics = str(diagnostics)[:8000]
        self.stage_label.configure(text=f"Startup failed: {str(message)[:180]}", text_color=self.theme["error"])
        self.progress.set(1)
        self.tip_label.configure(text="The main application was not opened. Sanitized local diagnostics may be copied for review.")
        self.failure_actions.grid()
        self.update_idletasks()

    def _copy_failure(self):
        self.clipboard_clear()
        self.clipboard_append(self.failure_diagnostics or self.stage_label.cget("text"))

    def close(self):
        if self.winfo_exists():
            self.destroy()
