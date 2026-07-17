import customtkinter as ctk


class GothicHeader(ctk.CTkFrame):

    def __init__(self, parent, theme):
        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.title = ctk.CTkLabel(
            self,
            text="⚔ SUS-ADB COMPANION ⚔",
            font=("Times New Roman", 34, "bold"),
            text_color=theme["gold"]
        )
        self.title.pack(pady=(5, 2))

        self.subtitle = ctk.CTkLabel(
            self,
            text="Medieval Gothic Blackhat Console",
            font=("Times New Roman", 16, "italic"),
            text_color=theme["muted"]
        )
        self.subtitle.pack(pady=(0, 8))

        self.separator = ctk.CTkFrame(
            self,
            fg_color=theme["gold_dark"],
            height=2
        )
        self.separator.pack(fill="x", padx=120, pady=(0, 6))