import customtkinter as ctk
from app.widgets.gothic_button import GothicButton
from app.widgets.gothic_frame import GothicFrame
from app.widgets.gothic_label import GothicLabel
from app.widgets.device_card import DeviceCard
from app.widgets.status_bar import StatusBar




class CommandBar(GothicFrame):

    def __init__(self, parent, execute_callback):

        super().__init__(parent)

        self.execute_callback = execute_callback

        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(

            self,

            placeholder_text="Enter ADB command..."

        )

        self.entry.grid(

            row=0,

            column=0,

            sticky="ew",

            padx=(10,5),

            pady=10

        )

        self.entry.bind(
            "<Return>",
            self.run
        )

        self.run_button = GothicButton(

            self,

            text="Run",

            width=100,

            command=self.run

        )

        self.run_button.grid(

            row=0,

            column=1,

            padx=(5,10),

            pady=10

        )


    def run(self, event=None):

        command = self.entry.get().strip()

        if command:

            self.execute_callback(command)

            self.entry.delete(0, "end")