import customtkinter as ctk
from app.core.app_metadata import METADATA


class GothicHeader(ctk.CTkFrame):

    def __init__(
        self,
        parent,
        theme,
        home_callback=None,
        help_callback=None,
        mode_callback=None,
        interface_mode="guided",
    ):
        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.title = ctk.CTkLabel(
            self,
            text=f"⚔ {METADATA.display_mark} ⚔",
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
            text=f"{METADATA.descriptor} · {METADATA.version}",
            font=("Times New Roman", 16, "italic"),
            text_color=theme["muted"]
        )
        self.subtitle.pack(pady=(0, 8))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=120, pady=(0, 5))
        controls.grid_columnconfigure(0, weight=1)
        self.mode = ctk.CTkSegmentedButton(
            controls,
            values=["Guided", "Advanced"],
            command=lambda value: mode_callback(value.casefold())
            if mode_callback else None,
            selected_color=theme["red"],
            selected_hover_color=theme["red_hover"],
            unselected_color=theme["panel_alt"],
            unselected_hover_color=theme["gold_dark"],
            text_color=theme["text"],
            width=210,
        )
        self.mode.grid(row=0, column=1, padx=6)
        self.mode.set(
            "Advanced" if interface_mode == "advanced" else "Guided"
        )
        self.help_button = ctk.CTkButton(
            controls,
            text="Help",
            command=help_callback,
            width=90,
            fg_color=theme["red"],
            hover_color=theme["red_hover"],
            text_color=theme["text"],
            border_width=1,
            border_color=theme["gold_dark"],
        )
        self.help_button.grid(row=0, column=2, padx=6)

        self.separator = ctk.CTkFrame(
            self,
            fg_color=theme["gold_dark"],
            height=2
        )
        self.separator.pack(fill="x", padx=120, pady=(0, 6))
