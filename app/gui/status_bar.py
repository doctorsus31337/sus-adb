import customtkinter as ctk


class StatusBar(ctk.CTkFrame):

    def __init__(self, parent, theme):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=8,
            height=42
        )

        self.theme = theme

        self.pack_propagate(False)

        self.label = ctk.CTkLabel(
            self,
            text="ADB: Idle    |    Frida: Unknown    |    Device: None    |    Root: Unknown",
            font=("Segoe UI", 13, "bold"),
            text_color=theme["gold"]
        )
        self.label.pack(fill="x", padx=15, pady=8)

    def set_status(self, adb=None, frida=None, device=None, root=None):

        current = {
            "adb": "Idle",
            "frida": "Unknown",
            "device": "None",
            "root": "Unknown"
        }

        if adb is not None:
            current["adb"] = adb

        if frida is not None:
            current["frida"] = frida

        if device is not None:
            current["device"] = device

        if root is not None:
            current["root"] = root

        self.label.configure(
            text=f"ADB: {current['adb']}    |    Frida: {current['frida']}    |    Device: {current['device']}    |    Root: {current['root']}"
        )