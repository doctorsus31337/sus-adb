"""Selectable device summary card."""

import customtkinter as ctk

from app.core.device import Device


class DeviceCard(ctk.CTkFrame):
    def __init__(self, parent, device: Device, theme, select_callback=None):
        super().__init__(
            parent,
            fg_color=theme["panel_alt"],
            corner_radius=9,
            border_width=1,
            border_color=theme["border"],
        )
        self.device = device
        self.select_callback = select_callback

        title = ctk.CTkLabel(
            self,
            text=device.display_name,
            font=("Segoe UI", 14, "bold"),
            text_color=theme["gold"],
            anchor="w",
        )
        title.pack(fill="x", padx=10, pady=(8, 0))

        details = ctk.CTkLabel(
            self,
            text=(
                f"{device.serial}\n"
                f"Android {device.android_version}  •  Battery {device.battery}\n"
                f"State: {device.state}  •  Root: {self._yes_no(device.root)}  •  Frida: {self._yes_no(device.frida)}"
            ),
            font=("Consolas", 11),
            text_color=theme["text"],
            justify="left",
            anchor="w",
        )
        details.pack(fill="x", padx=10, pady=(2, 8))

        for widget in (self, title, details):
            widget.bind("<Button-1>", self._select)

    @staticmethod
    def _yes_no(value: bool | None) -> str:
        if value is None:
            return "Unknown"
        return "Yes" if value else "No"

    def _select(self, _event=None):
        if self.select_callback is not None:
            self.select_callback(self.device.serial)
