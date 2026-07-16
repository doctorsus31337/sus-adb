"""
sus-adb Main GUI Window
"""

import customtkinter as ctk

from app.gui.theme import get_theme
from app.core.adb_manager import ADBManager
from app.core.worker import BackgroundWorker


class SusADBWindow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.theme = get_theme()

        self.adb = ADBManager()

        self.title("SUS-ADB Companion")

        self.geometry("1400x800")

        self.minsize(1200, 700)

        self.configure(
            fg_color=self.theme["bg"]
        )

        self.create_widgets()

        self.refresh_devices()

    ############################################################

    def create_widgets(self):

        #
        # Header
        #

        self.header = ctk.CTkLabel(
            self,
            text="SUS-ADB Companion",
            font=("Times New Roman", 42, "bold"),
            text_color=self.theme["gold"]
        )

        self.header.pack(
            pady=(20, 0)
        )

        self.subtitle = ctk.CTkLabel(
            self,
            text="Android Reverse Engineering Companion",
            font=("Times New Roman", 18),
            text_color=self.theme["text"]
        )

        self.subtitle.pack(
            pady=(0, 20)
        )

        ########################################################

        self.main_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.main_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=10
        )

        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=3)
        self.main_frame.grid_columnconfigure(2, weight=1)

        self.main_frame.grid_rowconfigure(0, weight=1)

        ########################################################
        #
        # LEFT PANEL
        #
        ########################################################

        self.left_frame = ctk.CTkFrame(self.main_frame)

        self.left_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 10)
        )

        device_label = ctk.CTkLabel(
            self.left_frame,
            text="ADB Devices",
            font=("Arial", 20, "bold")
        )

        device_label.pack(pady=10)

        self.device_list = ctk.CTkTextbox(
            self.left_frame,
            width=250,
            height=450
        )

        self.device_list.pack(
            padx=10,
            pady=10,
            fill="both",
            expand=True
        )

        self.refresh_button = ctk.CTkButton(
            self.left_frame,
            text="Refresh Devices",
            command=self.refresh_devices
        )

        self.refresh_button.pack(
            padx=10,
            pady=(5, 5),
            fill="x"
        )

        self.connect_button = ctk.CTkButton(
            self.left_frame,
            text="Connect",
            command=self.connect_device
        )

        self.connect_button.pack(
            padx=10,
            pady=(0, 10),
            fill="x"
        )

        ########################################################
        #
        # CENTER PANEL
        #
        ########################################################

        self.center_frame = ctk.CTkFrame(self.main_frame)

        self.center_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=10
        )

        console_label = ctk.CTkLabel(
            self.center_frame,
            text="Console",
            font=("Arial", 20, "bold")
        )

        console_label.pack(pady=10)

        self.console = ctk.CTkTextbox(
            self.center_frame
        )

        self.console.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        ########################################################
        #
        # RIGHT PANEL
        #
        ########################################################

        self.right_frame = ctk.CTkFrame(self.main_frame)

        self.right_frame.grid(
            row=0,
            column=2,
            sticky="nsew",
            padx=(10, 0)
        )

        info_label = ctk.CTkLabel(
            self.right_frame,
            text="Information",
            font=("Arial", 20, "bold")
        )

        info_label.pack(
            pady=10
        )

        self.info = ctk.CTkTextbox(
            self.right_frame,
            width=250
        )

        self.info.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        self.info.insert(
            "end",
            "Select a device to view information.\n"
        )

        ########################################################

        self.status = ctk.CTkLabel(
            self,
            text="Ready",
            anchor="w"
        )

        self.status.pack(
            fill="x",
            padx=15,
            pady=(0, 10)
        )

    ############################################################

    def log(self, text):

        self.console.insert(
            "end",
            text + "\n"
        )

        self.console.see("end")

    ############################################################

    def refresh_devices(self):

        self.status.configure(
            text="Scanning for ADB devices..."
        )

        self.log("[INFO] Searching for connected devices...")

        worker = BackgroundWorker(
            target=self.adb.devices,
            callback=self.populate_devices
        )

        worker.start()

    ############################################################

    def populate_devices(self, devices):

        self.device_list.delete(
            "1.0",
            "end"
        )

        if len(devices) == 0:

            self.device_list.insert(
                "end",
                "No devices found."
            )

            self.log("[WARN] No ADB devices detected.")

            self.status.configure(
                text="No devices detected."
            )

            return

        for device in devices:

            self.device_list.insert(
                "end",
                device + "\n"
            )

            self.log(
                f"[OK] Found device: {device}"
            )

        self.status.configure(
            text=f"{len(devices)} device(s) connected."
        )

    ############################################################

    def connect_device(self):

        self.log(
            "[INFO] Connect button pressed."
        )

        self.status.configure(
            text="Connection feature coming next..."
        )