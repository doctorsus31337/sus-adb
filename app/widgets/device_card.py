"""Selectable device summary card."""

import customtkinter as ctk

from app.core.device import Device


class DeviceCard(ctk.CTkFrame):
    VALUE_WRAP_LENGTH = 165

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
        self.grid_columnconfigure(1, weight=1)

        model = ctk.CTkLabel(
            self,
            text=device.display_name,
            font=("Segoe UI", 14, "bold"),
            text_color=theme["gold"],
            anchor="w",
            justify="left",
            wraplength=210,
        )
        model.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=10,
            pady=(8, 4),
        )

        widgets = [model]
        fields = (
            ("Serial", device.serial),
            ("Android", device.android_version),
            ("Battery", device.battery),
            ("State", device.state),
            ("Root", self._yes_no(device.root)),
            ("Frida", self._yes_no(device.frida)),
        )
        for row, (name, value) in enumerate(fields, start=1):
            name_label = ctk.CTkLabel(
                self,
                text=f"{name}:",
                font=("Segoe UI", 11, "bold"),
                text_color=theme["muted"],
                anchor="nw",
            )
            name_label.grid(
                row=row,
                column=0,
                sticky="nw",
                padx=(10, 6),
                pady=(1, 7 if row == len(fields) else 1),
            )

            value_label = ctk.CTkLabel(
                self,
                text=str(value),
                font=("Consolas", 11),
                text_color=theme["text"],
                justify="left",
                anchor="nw",
                wraplength=self.VALUE_WRAP_LENGTH,
            )
            value_label.grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(0, 10),
                pady=(1, 7 if row == len(fields) else 1),
            )
            widgets.extend((name_label, value_label))

        for widget in (self, *widgets):
            widget.bind("<Button-1>", self._select)

    @staticmethod
    def _yes_no(value: bool | None) -> str:
        if value is None:
            return "Unknown"
        return "Yes" if value else "No"

    def _select(self, _event=None):
        if self.select_callback is not None:
            self.select_callback(self.device.serial)
