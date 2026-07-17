import customtkinter as ctk


class DeviceCard(ctk.CTkFrame):

    def __init__(self, parent, device):

        super().__init__(

            parent,

            fg_color="#222222",

            corner_radius=10,

            border_width=1,

            border_color="#393939"

        )

        name = ctk.CTkLabel(

            self,

            text=device,

            font=("Segoe UI", 14, "bold")

        )

        name.pack(

            anchor="w",

            padx=12,

            pady=(10, 2)

        )

        status = ctk.CTkLabel(

            self,

            text="USB Connected",

            text_color="#56b870",

            font=("Segoe UI", 12)

        )

        status.pack(

            anchor="w",

            padx=12,

            pady=(0, 10)

        )