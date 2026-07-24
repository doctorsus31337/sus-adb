"""Compact host-owned selected-device control for addon windows."""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from app.core.host_state import HostStateSnapshot


class AddonDeviceSelector(ctk.CTkFrame):
    PLACEHOLDER = "Select a device"

    def __init__(
        self,
        parent,
        theme,
        *,
        select_callback,
        refresh_callback,
    ):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["gold_dark"],
        )
        self.theme = theme
        self.select_callback = select_callback
        self.refresh_callback = refresh_callback
        self._label_to_serial: dict[str, str] = {}
        self._refreshing = False
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self, text="Device:", text_color=theme["muted"], font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=0, padx=(10, 5), pady=8)
        self.selector = ctk.CTkComboBox(
            self,
            values=[self.PLACEHOLDER],
            state="readonly",
            command=self._selected,
            fg_color=theme["terminal_bg"],
            border_color=theme["gold_dark"],
            button_color=theme["red"],
            button_hover_color=theme["red_hover"],
            dropdown_fg_color=theme["panel_alt"],
            dropdown_hover_color=theme["red"],
            text_color=theme["text"],
            dropdown_text_color=theme["text"],
        )
        self.selector.grid(row=0, column=1, sticky="ew", padx=5, pady=8)
        self.selector.set(self.PLACEHOLDER)
        self.refresh_button = ctk.CTkButton(
            self,
            text="⟳ Refresh Devices",
            command=self.refresh,
            fg_color=theme["red"],
            hover_color=theme["red_hover"],
            text_color=theme["text"],
            border_width=1,
            border_color=theme["gold_dark"],
            width=150,
        )
        self.refresh_button.grid(row=0, column=2, padx=(5, 10), pady=8)
        self.status = ctk.CTkLabel(
            self,
            text="Not refreshed",
            text_color=theme["muted"],
            anchor="w",
        )
        self.status.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 6))

    @staticmethod
    def _device_label(device) -> str:
        name = device.display_name or device.model or device.serial
        return f"{name} — {device.serial} [{device.state}]"

    def apply_snapshot(self, snapshot: HostStateSnapshot) -> None:
        self._label_to_serial = {
            self._device_label(device): device.serial for device in snapshot.devices
        }
        values = list(self._label_to_serial) or [self.PLACEHOLDER]
        self.selector.configure(values=values)
        selected = next(
            (label for label, serial in self._label_to_serial.items()
             if serial == snapshot.selected_serial),
            self.PLACEHOLDER,
        )
        self.selector.set(selected)
        if snapshot.lifecycle in {"device-refresh-started", "device-refreshing"}:
            self._set_loading(True)
            self.status.configure(text="Scanning ADB devices…", text_color=self.theme["gold"])
        else:
            self._set_loading(False)
            stamp = datetime.fromisoformat(snapshot.updated_at).astimezone().strftime("%H:%M:%S")
            selected_state = (
                snapshot.selected_device.state if snapshot.selected_device else "no explicit selection"
            )
            self.status.configure(
                text=f"ADB: {snapshot.adb_state} · {selected_state} · refreshed {stamp}",
                text_color=self.theme["gold"] if snapshot.selected_device else self.theme["muted"],
            )

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._set_loading(True)
        accepted = self.refresh_callback()
        if accepted is False:
            self._set_loading(False)

    def _set_loading(self, loading: bool) -> None:
        self._refreshing = loading
        self.refresh_button.configure(
            state="disabled" if loading else "normal",
            text="Scanning…" if loading else "⟳ Refresh Devices",
        )
        self.selector.configure(state="disabled" if loading else "readonly")

    def _selected(self, label: str) -> None:
        serial = self._label_to_serial.get(label)
        if serial:
            self.select_callback(serial)
