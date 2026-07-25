"""Compact host-owned device strip with an explicit selector drawer."""

from __future__ import annotations

import customtkinter as ctk

from app.core.device import Device
from app.core.workspace_navigation import abbreviated_serial
from app.gui.customtkinter_compat import focused_within, safe_focus


class DeviceDockRow(ctk.CTkFrame):
    def __init__(self, parent, theme, device, command):
        super().__init__(
            parent,
            fg_color=theme["panel_alt"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=8,
        )
        self.theme = theme
        self.device = device
        self.command = command
        self.grid_columnconfigure(0, weight=1)
        self.select_button = ctk.CTkButton(
            self,
            text="",
            command=lambda: self.command(self.device.serial),
            anchor="w",
            height=42,
            fg_color=theme["panel_alt"],
            hover_color=theme["gold_dark"],
            text_color=theme["text"],
            border_width=0,
        )
        self.select_button.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self.select_button._canvas.configure(takefocus=True)
        self.update_device(device, selected=False)

    def update_device(self, device, selected):
        self.device = device
        self.select_button.configure(
            text=(
                f"{device.display_name} — {device.serial}\n"
                f"{device.connection_mode} · {device.state}"
            ),
            fg_color=self.theme["red"] if selected else self.theme["panel_alt"],
            border_width=1 if selected else 0,
            border_color=self.theme["gold"] if selected else self.theme["border"],
        )


class DeviceDock(ctk.CTkFrame):
    """Presentation-only device dock; all operations stay host-owned."""

    def __init__(
        self,
        parent,
        theme,
        refresh_callback,
        connect_callback,
        select_callback,
        *,
        expanded=False,
        expanded_callback=None,
    ):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=9,
        )
        self.theme = theme
        self.refresh_callback = refresh_callback
        self.connect_callback = connect_callback
        self.select_callback = select_callback
        self.expanded_callback = expanded_callback
        self._selected_serial = None
        self._devices = {}
        self.rows = {}
        self._expanded = False
        self.grid_columnconfigure(0, weight=1)
        self.summary = ctk.CTkFrame(self, fg_color="transparent")
        self.summary.grid(row=0, column=0, sticky="ew", padx=7, pady=5)
        self.summary.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self.summary,
            text="◆",
            width=30,
            text_color=theme["gold"],
            font=("Times New Roman", 18, "bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(3, 7))
        self.name_label = ctk.CTkLabel(
            self.summary,
            text="No device selected",
            text_color=theme["text"],
            anchor="w",
            font=("Segoe UI", 13, "bold"),
        )
        self.name_label.grid(row=0, column=1, sticky="ew")
        self.serial_label = ctk.CTkLabel(
            self.summary,
            text="Select explicitly from the device drawer",
            text_color=theme["muted"],
            anchor="w",
            font=("Consolas", 10),
        )
        self.serial_label.grid(row=1, column=1, sticky="ew")
        self.state_badge = ctk.CTkLabel(
            self.summary,
            text="ADB unavailable",
            text_color=theme["muted"],
            fg_color=theme["panel_alt"],
            corner_radius=7,
            width=112,
        )
        self.state_badge.grid(row=0, column=2, rowspan=2, padx=5)
        self.refresh_button = self._button(
            self.summary, "Refresh", self.refresh_callback, 3
        )
        self.select_button = self._button(
            self.summary, "Select Device", self.expand, 4
        )
        self.expand_button = self._button(
            self.summary, "Details ▾", self.toggle, 5
        )
        self.drawer = ctk.CTkFrame(
            self,
            fg_color=theme["panel_alt"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=8,
            height=172,
        )
        self.drawer.grid_propagate(False)
        self.drawer.grid_columnconfigure(0, weight=1)
        self.drawer.grid_rowconfigure(1, weight=1)
        drawer_header = ctk.CTkFrame(self.drawer, fg_color="transparent")
        drawer_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        drawer_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            drawer_header,
            text="Connected Devices",
            text_color=theme["gold"],
            font=("Times New Roman", 17, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            drawer_header,
            text="Selection is always explicit.",
            text_color=theme["muted"],
            anchor="e",
        ).grid(row=0, column=1, sticky="e")
        self.device_list = ctk.CTkScrollableFrame(
            self.drawer,
            height=120,
            fg_color=theme["terminal_bg"],
            scrollbar_button_color=theme["gold_dark"],
            scrollbar_button_hover_color=theme["red_hover"],
        )
        self.device_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.device_list.grid_columnconfigure(0, weight=1)
        controls = ctk.CTkFrame(self.drawer, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 7))
        controls.grid_columnconfigure(0, weight=1)
        self.drawer_status = ctk.CTkLabel(
            controls,
            text="No devices detected.",
            text_color=theme["muted"],
            anchor="w",
        )
        self.drawer_status.grid(row=0, column=0, sticky="ew")
        self.connect_button = self._button(
            controls, "Connect / Diagnose", self._connect, 1
        )
        self.close_button = self._button(controls, "Close", self.collapse, 2)
        if expanded:
            self.expand()
        else:
            self.drawer.grid_remove()

    def _button(self, parent, text, command, column):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=31,
            fg_color=self.theme["panel_alt"],
            hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
            border_width=1,
            border_color=self.theme["gold_dark"],
        )
        button.grid(row=0, column=column, rowspan=2, padx=3, sticky="e")
        button._canvas.configure(takefocus=True)
        return button

    @property
    def selected_serial(self):
        return self._selected_serial

    @selected_serial.setter
    def selected_serial(self, value):
        self._selected_serial = value or None
        self._render_selection()

    @property
    def expanded(self):
        return self._expanded

    def set_refreshing(self, refreshing):
        self.refresh_button.configure(
            state="disabled" if refreshing else "normal",
            text="Refreshing…" if refreshing else "Refresh",
        )

    def update_devices(self, devices: list[Device]):
        self._devices = {device.serial: device for device in devices}
        if self._selected_serial not in self._devices:
            self._selected_serial = None
        for serial in tuple(self.rows):
            if serial not in self._devices:
                row = self.rows.pop(serial)
                if focused_within(row):
                    safe_focus(self.select_button)
                row.destroy()
        for serial, device in self._devices.items():
            row = self.rows.get(serial)
            if row is None:
                row = DeviceDockRow(
                    self.device_list, self.theme, device, self.select_device
                )
                self.rows[serial] = row
            row.update_device(device, serial == self._selected_serial)
        for index, serial in enumerate(self._devices):
            self.rows[serial].grid(
                row=index, column=0, sticky="ew", padx=3, pady=3
            )
        self.drawer_status.configure(
            text=(
                f"{len(devices)} device{'s' if len(devices) != 1 else ''} found."
                if devices else "No devices detected. Refresh explicitly."
            )
        )
        self._render_selection()

    def select_device(self, serial):
        accepted = self.select_callback(serial)
        if accepted is not False:
            self._selected_serial = serial
        self._render_selection()
        return accepted

    def _render_selection(self):
        selected = self._devices.get(self._selected_serial)
        if selected is None:
            self.name_label.configure(text="No device selected")
            self.serial_label.configure(
                text="Select explicitly from the device drawer"
            )
            self.state_badge.configure(
                text="ADB unavailable", text_color=self.theme["muted"]
            )
            self.select_button.configure(text="Select Device")
        else:
            self.name_label.configure(text=selected.display_name)
            self.serial_label.configure(
                text=f"Serial: {abbreviated_serial(selected.serial)}"
            )
            self.state_badge.configure(
                text=selected.connection_mode,
                text_color=(
                    self.theme["success"]
                    if selected.usable else self.theme["error"]
                    if selected.state in {"offline", "unauthorized"}
                    else self.theme["gold"]
                ),
            )
            self.select_button.configure(text="Change Device")
        for serial, row in self.rows.items():
            row.update_device(row.device, serial == self._selected_serial)

    def toggle(self):
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        if self._expanded:
            return
        self._expanded = True
        self.drawer.grid(row=1, column=0, sticky="ew", padx=7, pady=(0, 7))
        self.expand_button.configure(text="Details ▴")
        if self.expanded_callback:
            self.expanded_callback(True)

    def collapse(self):
        if not self._expanded:
            return False
        if focused_within(self.drawer):
            safe_focus(self.expand_button)
        self.drawer.grid_remove()
        self._expanded = False
        self.expand_button.configure(text="Details ▾")
        if self.expanded_callback:
            self.expanded_callback(False)
        return True

    def apply_interface_mode(self, _mode):
        self._render_selection()

    def _connect(self):
        return self.connect_callback(self._selected_serial)
