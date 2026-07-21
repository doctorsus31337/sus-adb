import customtkinter as ctk
from app.core.app_metadata import METADATA


class GothicHeader(ctk.CTkFrame):

    def __init__(self, parent, theme, home_callback=None):
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
        if home_callback:
            self.title.configure(cursor="hand2")
            self.title.bind("<Button-1>",lambda _event:home_callback())
            self.title.bind("<Return>",lambda _event:home_callback())
            self.title.bind("<space>",lambda _event:home_callback())
            self.title.bind("<Enter>",lambda _event:self.title.configure(text_color=theme["text"]))
            self.title.bind("<Leave>",lambda _event:self.title.configure(text_color=theme["gold"]))
            self.title.tooltip_text="Return to Console Home"

        self.subtitle = ctk.CTkLabel(
            self,
            text=f"Medieval Gothic Blackhat Console · {METADATA.version}",
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
