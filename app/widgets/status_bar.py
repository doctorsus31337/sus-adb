"""Persistent live status display for the main SUS Companion window."""

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, parent, theme):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=8,
            height=34,
        )
        self.theme = theme
        self.grid_propagate(False)
        self._status = {
            "adb": "Idle",
            "frida": "Unknown",
            "device": "None",
            "root": "Unknown",
        }
        self.interface_mode = "guided"

        self.label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 13, "bold"),
            text_color=theme["gold"],
        )
        self.label.pack(fill="x", padx=13, pady=5)
        self._render()

    def set_status(self, adb=None, frida=None, device=None, root=None):
        updates = {"adb": adb, "frida": frida, "device": device, "root": root}
        for key, value in updates.items():
            if value is not None:
                self._status[key] = str(value)
        self._render()

    def apply_interface_mode(self, mode):
        self.interface_mode = (
            mode if mode in {"guided", "advanced"} else "guided"
        )
        self._render()

    def _render(self):
        if self.interface_mode == "advanced":
            text = (
                f"ADB: {self._status['adb']}  ·  "
                f"Device: {self._status['device']}  ·  "
                f"Frida: {self._status['frida']}  ·  "
                f"Root: {self._status['root']}"
            )
        else:
            text = (
                f"ADB: {self._status['adb']}  ·  "
                f"Device: {self._status['device']}"
            )
        self.label.configure(text=text)
