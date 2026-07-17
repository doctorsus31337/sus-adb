import customtkinter as ctk


class GothicSeparator(ctk.CTkFrame):

    def __init__(self, parent):

        super().__init__(
            parent,
            height=2,
            fg_color="#7b5d1a",
            corner_radius=0
        )