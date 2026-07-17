import customtkinter as ctk

from app.widgets.gothic_frame import GothicFrame
from app.widgets.gothic_label import GothicLabel


class InfoCard(GothicFrame):

    def __init__(self, parent, title, value):

        super().__init__(parent)

        GothicLabel(

            self,

            text=title,

            font=("Segoe UI", 13, "bold")

        ).pack(anchor="w", padx=12, pady=(10, 0))

        self.value = ctk.CTkLabel(

            self,

            text=value,

            font=("Consolas", 15)

        )

        self.value.pack(anchor="w", padx=12, pady=(0, 10))

    def update_value(self, value):

        self.value.configure(text=value)