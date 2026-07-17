import customtkinter as ctk


class GothicFrame(ctk.CTkFrame):

    def __init__(self, parent, **kwargs):

        defaults = {

            "fg_color": "#171717",

            "corner_radius": 12,

            "border_width": 1,

            "border_color": "#2f2f2f"

        }

        defaults.update(kwargs)

        super().__init__(parent, **defaults)