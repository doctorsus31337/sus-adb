"""Persistent live status display for the main SUS-ADB window."""

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, parent, theme):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=8,
            height=42,
        )
        self.theme = theme
        self.grid_propagate(False)
        self._status = {
            "adb": "Idle",
            "frida": "Unknown",
            "device": "None",
            "root": "Unknown",
        }

        self.label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 13, "bold"),
            text_color=theme["gold"],
        )
        self.label.pack(fill="x", padx=15, pady=8)
        self._render()

    def set_status(self, adb=None, frida=None, device=None, root=None):
        updates = {"adb": adb, "frida": frida, "device": device, "root": root}
        for key, value in updates.items():
            if value is not None:
                self._status[key] = str(value)
        self._render()

    def _render(self):
        self.label.configure(
            text=(
                f"ADB: {self._status['adb']}    |    "
                f"Frida: {self._status['frida']}    |    "
                f"Device: {self._status['device']}    |    "
                f"Root: {self._status['root']}"
            )
        )
