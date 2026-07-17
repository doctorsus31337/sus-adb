import customtkinter as ctk


from app.widgets.gothic_button import GothicButton
from app.widgets.gothic_frame import GothicFrame
from app.widgets.gothic_label import GothicLabel
from app.widgets.device_card import DeviceCard
from app.widgets.status_bar import StatusBar


class DevicePanel(GothicFrame):

    def __init__(self, parent, theme, refresh_callback, connect_callback):

        super().__init__(parent)

        self.theme = theme

        self.refresh_callback = refresh_callback
        self.connect_callback = connect_callback

        self.configure(
            fg_color=theme["panel"]
        )

        self.grid_columnconfigure(0, weight=1)

        self.title = ctk.CTkLabel(
            self,
            text="Connected Devices",
            font=("Segoe UI", 18, "bold"),
            text_color=theme["gold"]
        )

        self.title.pack(
            pady=(10,5)
        )

        self.device_list = ctk.CTkTextbox(
            self,
            width=300,
            height=220
        )

        self.device_list.pack(
            padx=10,
            pady=5,
            fill="both",
            expand=True
        )

        self.refresh_button = GothicButton(
            self,
            text="Refresh Devices",
            command=self.refresh_callback
        )

        self.refresh_button.pack(
            padx=10,
            pady=(5,5),
            fill="x"
        )

        self.connect_button = GothicButton(
            self,
            text="Connect",
            command=self.connect_callback
        )

        self.connect_button.pack(
            padx=10,
            pady=(0,10),
            fill="x"
        )


    def update_devices(self, devices):

        self.device_list.delete("1.0","end")

        if not devices:

            self.device_list.insert(
                "end",
                "No devices detected."
            )

            return

        for device in devices:

            self.device_list.insert(
                "end",
                f"{device}\n"
            )