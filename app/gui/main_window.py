"""
sus-adb Main GUI Window
"""

import customtkinter as ctk

from app.gui.theme import get_theme
from app.core.adb_manager import ADBManager


class SusADBWindow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.theme = get_theme()

        # Initialize managers
        self.adb = ADBManager()

        # Window
        self.title("sus-adb | Android Device Companion")
        self.geometry("1100x700")
        self.configure(
            fg_color=self.theme["bg"]
        )

        self.create_widgets()

        self.log("[INFO] sus-adb initialized.")
        self.log("[INFO] Ready.")

    def create_widgets(self):

        #
        # Title
        #
        self.title_label = ctk.CTkLabel(
            self,
            text="sus-adb",
            font=("Times New Roman", 32, "bold"),
            text_color=self.theme["gold"]
        )

        self.title_label.pack(
            pady=(20, 10)
        )

        #
        # Toolbar Frame
        #
        self.toolbar = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.toolbar.pack(
            fill="x",
            padx=20,
            pady=10
        )

        #
        # Refresh Devices Button
        #
        self.refresh_button = ctk.CTkButton(
            self.toolbar,
            text="Refresh Devices",
            command=self.refresh_devices,
            width=170
        )

        self.refresh_button.pack(
            side="left",
            padx=5
        )

        #
        # Console
        #
        self.console = ctk.CTkTextbox(
            self,
            width=1000,
            height=470
        )

        self.console.pack(
            padx=20,
            pady=10,
            fill="both",
            expand=True
        )

        #
        # Status Bar
        #
        self.status = ctk.CTkLabel(
            self,
            text="Ready",
            text_color=self.theme["text"]
        )

        self.status.pack(
            side="bottom",
            pady=10
        )

    #
    # Logging
    #
    def log(self, message):

        self.console.insert("end", message + "\n")
        self.console.see("end")

    #
    # Refresh Device List
    #
    def refresh_devices(self):

        self.status.configure(
            text="Searching..."
        )

        self.log("")
        self.log("========================================")
        self.log("[INFO] Searching for connected devices...")
        self.log("")

        output = self.adb.devices()

        if output.strip():
            self.log(output)
        else:
            self.log("[WARNING] No output received from ADB.")

        self.log("========================================")

        self.status.configure(
            text="Ready"
        )