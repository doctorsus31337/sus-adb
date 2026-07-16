"""
sus-adb Main GUI Window
"""

import customtkinter as ctk

from app.gui.theme import get_theme
from app.gui.device_panel import DevicePanel
from app.gui.command_bar import CommandBar

from app.core.device_manager import DeviceManager
from app.core.terminal_manager import TerminalManager


class SusADBWindow(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.theme = get_theme()

        self.devices = DeviceManager()

        self.terminal = TerminalManager(self.log)

        self.title("SUS-ADB Companion")

        self.geometry("1350x850")

        self.configure(
            fg_color=self.theme["bg"]
        )

        self.create_widgets()


    def create_widgets(self):

        self.title_label = ctk.CTkLabel(

            self,

            text="SUS-ADB Companion",

            font=("Times New Roman", 42, "bold"),

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

        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

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

        right_side = ctk.CTkFrame(
            body,
            fg_color="transparent"
        )

        right_side.grid(

            row=0,

            column=1,

            sticky="nsew"

        )

        right_side.grid_rowconfigure(1, weight=1)
        right_side.grid_columnconfigure(0, weight=1)

        self.command_bar = CommandBar(

            right_side,

            self.execute_command

        )

        self.command_bar.grid(

            row=0,

            column=0,

            sticky="ew"

        )

        self.console = ctk.CTkTextbox(

            right_side

        )

        self.console.grid(

            row=1,

            column=0,

            sticky="nsew",

            padx=5,

            pady=(0,5)

        )

        self.console.insert(

            "end",

            "[INFO] SUS-ADB Companion initialized.\n"

        )

        self.status = ctk.CTkLabel(

            self,

            text="Ready"

        )

        self.status.pack(
            pady=10
        )


    def log(self, text):

        self.console.insert(
            "end",
            text + "\n"
        )

        self.console.see("end")


    def execute_command(self, command):

        self.terminal.execute(command)


    def refresh_devices(self):

        devices = self.devices.refresh()

        self.device_panel.update_devices(devices)

        self.log(
            f"[ADB] Found {len(devices)} device(s)."
        )


    def connect_device(self):

        self.log(
            "[ADB] Connect feature coming soon."
        )