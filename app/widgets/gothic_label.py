import customtkinter as ctk


class GothicLabel(ctk.CTkLabel):

    def __init__(self, parent, **kwargs):

        defaults = {

            "text_color": "#d6b55a",

            "font": ("Segoe UI", 16, "bold")

        }

        defaults.update(kwargs)

        super().__init__(parent, **defaults)