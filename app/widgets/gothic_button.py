import customtkinter as ctk


class GothicButton(ctk.CTkButton):

    def __init__(self, parent, **kwargs):

        defaults = {

            "fg_color": "#781010",

            "hover_color": "#a11717",

            "text_color": "#f2ddb2",

            "corner_radius": 8,

            "height": 42,

            "font": ("Segoe UI", 15, "bold"),

            "border_width": 2,\
            "border_color": "#3a1b1b"
        }

        defaults.update(kwargs)

        super().__init__(parent, **defaults)