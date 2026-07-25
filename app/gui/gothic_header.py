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
        self.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(4, 12), pady=(2, 5))
        self.title = ctk.CTkLabel(
            brand,
            text=f"⚔ {METADATA.display_mark} ⚔",
            font=("Times New Roman", 29, "bold"),
            text_color=theme["gold"],
            anchor="w",
        )
        self.title.grid(row=0, column=0, sticky="w")
        if home_callback:
            self.title.configure(cursor="hand2")
            self.title.bind("<Button-1>",lambda _event:home_callback())
            self.title.bind("<Return>",lambda _event:home_callback())
            self.title.bind("<space>",lambda _event:home_callback())
            self.title.bind("<Enter>",lambda _event:self.title.configure(text_color=theme["text"]))
            self.title.bind("<Leave>",lambda _event:self.title.configure(text_color=theme["gold"]))
            self.title._canvas.configure(takefocus=True)
            self.title.tooltip_text="Return to Workspace Home"

        self.subtitle = ctk.CTkLabel(
            brand,
            text=f"{METADATA.descriptor} · {METADATA.version}",
            font=("Times New Roman", 14, "italic"),
            text_color=theme["muted"],
            anchor="w",
        )
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(0, 1))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e", padx=(12, 4), pady=(2, 5))
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
            width=190,
        )
        self.mode.grid(row=0, column=0, padx=4)
        self.mode.set(
            "Advanced" if interface_mode == "advanced" else "Guided"
        )
        self.help_button = ctk.CTkButton(
            controls,
            text="Help",
            command=help_callback,
            width=90,
            fg_color=theme["panel_alt"],
            hover_color=theme["gold_dark"],
            text_color=theme["text"],
            border_width=1,
            border_color=theme["gold_dark"],
        )
        self.help_button.grid(row=0, column=1, padx=4)
        self.help_button._canvas.configure(takefocus=True)

        self.separator = ctk.CTkFrame(
            self,
            fg_color=theme["gold_dark"],
            height=2
        )
        self.separator.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 2)
        )
