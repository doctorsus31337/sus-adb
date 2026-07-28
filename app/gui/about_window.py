"""Themed, lazy, host-owned SUS Companion About window."""

from __future__ import annotations

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.core.branding_assets import ABOUT_ARTWORK
from app.gui.customtkinter_compat import (
    PendingCallbackOwner,
    ScopedScrollableFrame,
    safe_focus,
)


class AboutWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        theme,
        branding,
        *,
        metadata=METADATA,
        help_callback=None,
        on_close=None,
        width=760,
        height=590,
    ):
        super().__init__(parent)
        self.theme = theme
        self.branding = branding
        self.metadata = metadata
        self.help_callback = help_callback
        self.on_close = on_close
        self.callbacks = PendingCallbackOwner(self)
        self.title(f"About {metadata.application_name}")
        self.configure(fg_color=theme["bg"])
        self.minsize(680, 500)
        self.geometry(self._clamped_geometry(width, height))
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        branding.apply_window_icon(self)

        self.content = ScopedScrollableFrame(
            self,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["gold_dark"],
            corner_radius=12,
            scrollbar_button_color=theme["gold_dark"],
            scrollbar_button_hover_color=theme["red_hover"],
        )
        self.content.grid(row=0, column=0, sticky="nsew", padx=14, pady=(14, 6))
        self.content.grid_columnconfigure(0, weight=1)

        artwork = branding.ctk_image(ABOUT_ARTWORK, (230, 343))
        self.artwork_label = ctk.CTkLabel(
            self.content,
            text="" if artwork is not None else "⚔ SUS COMPANION ⚔",
            image=artwork,
            text_color=theme["gold"],
            font=("Times New Roman", 23, "bold"),
            width=230,
            height=343,
        )
        self.artwork_label.grid(row=0, column=0, sticky="n", padx=20, pady=(20, 12))
        self.artwork_image = artwork

        info = ctk.CTkFrame(self.content, fg_color="transparent")
        info.grid(row=1, column=0, sticky="new", padx=28, pady=(8, 24))
        info.grid_columnconfigure(0, weight=1)
        self.name_label = ctk.CTkLabel(
            info,
            text=metadata.application_name,
            text_color=theme["gold"],
            font=("Times New Roman", 31, "bold"),
            anchor="w",
        )
        self.name_label.grid(row=0, column=0, sticky="ew")
        self.version_label = ctk.CTkLabel(
            info,
            text=metadata.display_version,
            text_color=theme["text"],
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self.version_label.grid(row=1, column=0, sticky="ew", pady=(6, 2))
        ctk.CTkLabel(
            info,
            text=metadata.descriptor,
            text_color=theme["muted"],
            font=("Times New Roman", 16, "italic"),
            anchor="w",
            justify="left",
            wraplength=430,
        ).grid(row=2, column=0, sticky="ew", pady=(0, 18))
        self.mission_label = ctk.CTkLabel(
            info,
            text=(
                "A local-first workstation for authorized Android analysis, "
                "recovery, instrumentation, and repeatable operator-reviewed workflows."
            ),
            text_color=theme["text"],
            anchor="w",
            justify="left",
            wraplength=430,
        )
        self.mission_label.grid(row=3, column=0, sticky="ew", pady=(0, 18))
        self.build_label = ctk.CTkLabel(
            info,
            text=(
                f"Platform: {metadata.platform_name} · {metadata.architecture}\n"
                f"Build channel: {metadata.build_channel}\n"
                f"Revision: {metadata.short_revision}"
            ),
            text_color=theme["muted"],
            anchor="w",
            justify="left",
        )
        self.build_label.grid(row=4, column=0, sticky="ew", pady=(0, 18))
        self.attribution_label = ctk.CTkLabel(
            info,
            text=(
                "Legacy sus-adb commands and local storage remain compatible.\n\n"
                "Created by DoctorSUS & ChatGPT"
            ),
            text_color=theme["muted"],
            anchor="w",
            justify="left",
            wraplength=430,
        )
        self.attribution_label.grid(row=5, column=0, sticky="ew")

        controls = ctk.CTkFrame(
            self,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["gold_dark"],
            corner_radius=10,
        )
        controls.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        controls.grid_columnconfigure(0, weight=1)
        if help_callback is not None:
            self.help_button = ctk.CTkButton(
                controls,
                text="Help & Documentation",
                command=help_callback,
                fg_color=theme["panel_alt"],
                hover_color=theme["gold_dark"],
                text_color=theme["text"],
                border_width=1,
                border_color=theme["gold_dark"],
            )
            self.help_button.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        self.close_button = ctk.CTkButton(
            controls,
            text="Close",
            command=self.close,
            fg_color=theme["red"],
            hover_color=theme["red_hover"],
            text_color=theme["text"],
            width=110,
        )
        self.close_button.grid(row=0, column=1, sticky="e", padx=12, pady=10)
        self.callbacks.schedule_idle(safe_focus, self.close_button)

    def _clamped_geometry(self, width, height):
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = max(680, min(int(width), screen_w))
        height = max(500, min(int(height), screen_h))
        return (
            f"{width}x{height}+{max(0, (screen_w-width)//2)}"
            f"+{max(0, (screen_h-height)//2)}"
        )

    def close(self):
        if not self.winfo_exists():
            return
        self.callbacks.cancel_all()
        callback = self.on_close
        self.on_close = None
        self.destroy()
        if callback is not None:
            callback()
