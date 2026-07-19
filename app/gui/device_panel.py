"""Connected-device sidebar panel."""

import customtkinter as ctk

from app.core.device import Device
from app.widgets.device_card import DeviceCard
from app.widgets.gothic_button import GothicButton
from app.widgets.gothic_frame import GothicFrame


class DevicePanel(GothicFrame):
    def __init__(self, parent, theme, refresh_callback, connect_callback, select_callback=None):
        super().__init__(parent, fg_color=theme["panel"])
        self.theme = theme
        self.refresh_callback = refresh_callback
        self.connect_callback = connect_callback
        self.select_callback = select_callback
        self.selected_serial: str | None = None
        self.cards: list[DeviceCard] = []

        title = ctk.CTkLabel(
            self,
            text="Connected Devices",
            font=("Segoe UI", 18, "bold"),
            text_color=theme["gold"],
        )
        title.pack(pady=(10, 5))

        self.device_list = ctk.CTkScrollableFrame(
            self,
            width=285,
            height=220,
            fg_color=theme["terminal_bg"],
            border_width=1,
            border_color=theme["border"],
        )
        self.device_list.pack(fill="both", expand=True, padx=10, pady=5)

        self.empty_label = ctk.CTkLabel(
            self.device_list,
            text="No devices detected.",
            text_color=theme["muted"],
        )
        self.empty_label.pack(pady=20)

        GothicButton(
            self,
            text="Refresh Devices",
            command=self.refresh_callback,
        ).pack(fill="x", padx=10, pady=(5, 5))

        GothicButton(
            self,
            text="Connect / Diagnose",
            command=self._connect,
        ).pack(fill="x", padx=10, pady=(0, 10))

    def update_devices(self, devices: list[Device]):
        for widget in self.device_list.winfo_children():
            widget.destroy()
        self.cards.clear()

        if not devices:
            self.empty_label = ctk.CTkLabel(
                self.device_list,
                text="No devices detected.",
                text_color=self.theme["muted"],
            )
            self.empty_label.pack(pady=20)
            self.selected_serial = None
            return

        serials = {device.serial for device in devices}
        if self.selected_serial not in serials:
            self.selected_serial = devices[0].serial

        for device in devices:
            card = DeviceCard(
                self.device_list,
                device,
                self.theme,
                select_callback=self.select_device,
            )
            card.pack(fill="x", padx=3, pady=3)
            self.cards.append(card)

    def select_device(self, serial: str):
        self.selected_serial = serial
        if self.select_callback is not None:
            self.select_callback(serial)

    def _connect(self):
        self.connect_callback(self.selected_serial)
