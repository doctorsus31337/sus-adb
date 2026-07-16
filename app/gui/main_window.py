"""
sus-adb Main GUI Window
"""

import customtkinter as ctk

from app.gui.theme import get_theme
from app.gui.device_panel import DevicePanel

from app.core.device_manager import DeviceManager


class SusADBWindow(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.theme = get_theme()

        self.devices = DeviceManager()

        self.title("SUS-ADB Companion")

        self.geometry("1300x800")

        self.configure(
            fg_color=self.theme["bg"]
        )

        self.create_widgets()


    def create_widgets(self):

        self.title_label = ctk.CTkLabel(

            self,

            text="SUS-ADB Companion",

            font=("Times New Roman",40,"bold"),

            text_color=self.theme["gold"]

        )

        self.title_label.pack(
            pady=15
        )

        body = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        body.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=10
        )

        body.grid_columnconfigure(1,weight=1)

        self.device_panel = DevicePanel(

            body,

            self.theme,

            self.refresh_devices,

            self.connect_device

        )

        self.device_panel.grid(
            row=0,
            column=0,
            sticky="ns",
            padx=(0,15)
        )

        self.console = ctk.CTkTextbox(
            body
        )

        self.console.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        self.console.insert(
            "end",
            "[INFO] SUS-ADB Companion started.\n"
        )

        self.status = ctk.CTkLabel(
            self,
            text="Ready",
            text_color=self.theme["text"]
        )

        self.status.pack(
            pady=8
        )


    def log(self,text):

        self.console.insert(
            "end",
            text + "\n"
        )

        self.console.see("end")


    def refresh_devices(self):

        devices = self.devices.refresh()

        self.device_panel.update_devices(
            devices
        )

        self.log(
            f"[ADB] Found {len(devices)} device(s)."
        )


    def connect_device(self):

        self.log(
            "[ADB] Connect button pressed."
        )

        self.status.configure(
            text="Ready for future connection manager."
        )