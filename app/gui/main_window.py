"""
sus-adb Main GUI Window
"""

import customtkinter as ctk

from app.gui.theme import get_theme


class SusADBWindow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.theme = get_theme()

        self.title("sus-adb | Android Device Companion")

        self.geometry("1100x700")

        self.configure(
            fg_color=self.theme["bg"]
        )

        self.create_widgets()


    def create_widgets(self):

        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text="sus-adb",
            font=("Times New Roman", 32, "bold"),
            text_color=self.theme["gold"]
        )

        self.title_label.pack(
            pady=20
        )


        # Console
        self.console = ctk.CTkTextbox(
            self,
            width=1000,
            height=400
        )

        self.console.pack(
            padx=20,
            pady=20
        )


        self.console.insert(
            "end",
            "[INFO] sus-adb initializing...\n"
        )


        # Status bar

        self.status = ctk.CTkLabel(
            self,
            text="Ready",
            text_color=self.theme["text"]
        )

        self.status.pack(
            side="bottom",
            pady=10
        )