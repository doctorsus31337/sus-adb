import customtkinter as ctk

from app.widgets.gothic_button import GothicButton
from app.widgets.gothic_frame import GothicFrame


class CommandBar(GothicFrame):
    def __init__(self, parent, execute_callback):
        super().__init__(parent)
        self.execute_callback = execute_callback
        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter ADB command...",
        )
        self.entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(10, 5),
            pady=10,
        )
        self.entry.bind("<Return>", self.run)

        self.run_button = GothicButton(
            self,
            text="Run",
            width=100,
            command=self.run,
        )
        self.run_button.grid(
            row=0,
            column=1,
            padx=(5, 10),
            pady=10,
        )

        self.session_prompt = ctk.CTkFrame(self, fg_color="transparent")
        self.session_prompt.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=10,
            pady=(0, 8),
        )
        self.session_prompt.grid_columnconfigure(0, weight=1)
        self.session_label = ctk.CTkLabel(
            self.session_prompt,
            text="This command opens an interactive session.",
            text_color="#D6B55A",
            anchor="w",
        )
        self.session_label.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.open_session_button = GothicButton(
            self.session_prompt,
            text="Open Dedicated Session",
            width=180,
        )
        self.open_session_button.grid(row=0, column=1, padx=4)
        self.cancel_session_button = GothicButton(
            self.session_prompt,
            text="Cancel",
            width=90,
            command=self.hide_session_prompt,
        )
        self.cancel_session_button.grid(row=0, column=2, padx=4)
        self.session_prompt.grid_remove()

    def run(self, event=None):
        command = self.entry.get().strip()
        if command:
            self.execute_callback(command)
            self.entry.delete(0, "end")

    def show_session_prompt(self, route, open_callback):
        self.session_label.configure(
            text=f"This command opens an interactive session.\n{route.reason}"
        )
        self.open_session_button.configure(
            command=lambda: self._open_session(route, open_callback)
        )
        self.session_prompt.grid()

    def _open_session(self, route, callback):
        self.session_prompt.grid_remove()
        callback(route)

    def hide_session_prompt(self):
        self.session_prompt.grid_remove()
