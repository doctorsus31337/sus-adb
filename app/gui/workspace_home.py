"""Lightweight, responsive landing workspace for SUS Companion."""

from __future__ import annotations

import customtkinter as ctk

from app.core.workspace_navigation import WorkspaceHomeState


class WorkspaceHomeCard(ctk.CTkFrame):
    def __init__(self, parent, theme, mark, title, description, command):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=12,
        )
        self.theme = theme
        self.command = command
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.mark = ctk.CTkLabel(
            self,
            text=mark,
            width=42,
            text_color=theme["gold"],
            font=("Times New Roman", 24, "bold"),
        )
        self.mark.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=(13, 2))
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            text_color=theme["gold"],
            font=("Times New Roman", 19, "bold"),
            anchor="w",
        )
        self.title_label.grid(
            row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 1)
        )
        self.description_label = ctk.CTkLabel(
            self,
            text=description,
            text_color=theme["text"],
            anchor="nw",
            justify="left",
            wraplength=330,
        )
        self.description_label.grid(
            row=2, column=0, columnspan=2, sticky="nsew",
            padx=14, pady=(8, 5),
        )
        self.state_label = ctk.CTkLabel(
            self,
            text="Ready",
            text_color=theme["muted"],
            anchor="w",
            justify="left",
            wraplength=300,
        )
        self.state_label.grid(
            row=3, column=0, columnspan=2, sticky="ew",
            padx=14, pady=(2, 8),
        )
        self.open_button = ctk.CTkButton(
            self,
            text="Open",
            command=command,
            height=34,
            fg_color=theme["red"],
            hover_color=theme["red_hover"],
            text_color=theme["text"],
            border_width=1,
            border_color=theme["gold_dark"],
        )
        self.open_button.grid(
            row=4, column=0, columnspan=2, sticky="ew",
            padx=14, pady=(1, 13),
        )
        self.open_button._canvas.configure(takefocus=True)
        self.open_button.bind("<Return>", lambda _event: self._activate())
        self.open_button.bind("<space>", lambda _event: self._activate())

    def _activate(self):
        self.command()
        return "break"

    def set_state(self, text):
        self.state_label.configure(text=text or "Ready")

    def set_description(self, text):
        self.description_label.configure(text=text)


class WorkspaceHome(ctk.CTkFrame):
    CARD_SPECS = (
        ("Console", "›_", "Run one-shot commands and review local output."),
        (
            "Instrumentation",
            "⟐",
            "Choose an application and open an explicit observation workflow.",
        ),
        (
            "Device Recovery",
            "✚",
            "Recover selected files through the reviewed Device Rescue addon.",
        ),
        (
            "Script Studio",
            "§",
            "Edit, validate, and explicitly load local Frida scripts.",
        ),
        (
            "Pentest",
            "⚔",
            "Work inside an authorized assessment scope.",
        ),
        (
            "Sessions",
            "⌘",
            "Control dedicated ADB, Frida, and Objection terminals.",
        ),
    )

    GUIDED_DESCRIPTIONS = {
        spec[0]: spec[2] for spec in CARD_SPECS
    }
    ADVANCED_DESCRIPTIONS = {
        "Console": "One-shot command router and bounded command output.",
        "Instrumentation": "ADB applications, Frida targets, routes, and launch plans.",
        "Device Recovery": "Serial-bound scan, queue, resume, and manifest workflow.",
        "Script Studio": "Local library, runtime session, events, RPC, and profiles.",
        "Pentest": "Scoped case, evidence, findings, changes, and operational tools.",
        "Sessions": "Tracked external interactive-session lifecycle controller.",
    }

    def __init__(self, parent, theme, actions, explore_actions):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme = theme
        self.actions = dict(actions)
        self.state = WorkspaceHomeState()
        self.cards = {}
        self._columns = 0
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=theme["bg"],
            scrollbar_button_color=theme["gold_dark"],
            scrollbar_button_hover_color=theme["red_hover"],
        )
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(
            self.scroll,
            text="Workspace Home",
            text_color=theme["gold"],
            font=("Times New Roman", 28, "bold"),
            anchor="w",
        )
        self.heading.grid(row=0, column=0, sticky="ew", padx=16, pady=(13, 1))
        self.intro = ctk.CTkLabel(
            self.scroll,
            text="Choose one workspace. Nothing scans or executes from this screen.",
            text_color=theme["muted"],
            anchor="w",
        )
        self.intro.grid(row=1, column=0, sticky="ew", padx=16, pady=(1, 8))
        self.recommendation = ctk.CTkLabel(
            self.scroll,
            text="Recommended next step: select a device, or open Console to work locally.",
            text_color=theme["text"],
            fg_color=theme["panel_alt"],
            corner_radius=8,
            anchor="w",
            justify="left",
        )
        self.recommendation.grid(
            row=2, column=0, sticky="ew", padx=16, pady=(2, 10), ipady=5
        )
        self.card_grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.card_grid.grid(row=3, column=0, sticky="ew", padx=10)
        for title, mark, description in self.CARD_SPECS:
            self.cards[title] = WorkspaceHomeCard(
                self.card_grid,
                theme,
                mark,
                title,
                description,
                self.actions[title],
            )
        explore = ctk.CTkFrame(self.scroll, fg_color="transparent")
        explore.grid(row=4, column=0, sticky="ew", padx=16, pady=(13, 16))
        explore.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            explore,
            text="Explore",
            text_color=theme["gold"],
            font=("Times New Roman", 18, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.explore_bar = ctk.CTkFrame(explore, fg_color="transparent")
        self.explore_bar.grid(row=1, column=0, sticky="ew")
        self.explore_buttons = []
        for column, (title, command) in enumerate(explore_actions):
            self.explore_bar.grid_columnconfigure(column, weight=1)
            button = ctk.CTkButton(
                self.explore_bar,
                text=title,
                command=command,
                height=31,
                fg_color=theme["panel_alt"],
                hover_color=theme["gold_dark"],
                text_color=theme["text"],
                border_width=1,
                border_color=theme["gold_dark"],
            )
            button.grid(row=0, column=column, sticky="ew", padx=3)
            button._canvas.configure(takefocus=True)
            self.explore_buttons.append(button)
        self.card_grid.bind("<Configure>", self._layout_cards, add="+")
        self.after_idle(self._layout_cards)

    def _layout_cards(self, _event=None):
        width = max(1, self.card_grid.winfo_width())
        columns = 3 if width >= 990 else 2 if width >= 620 else 1
        if columns == self._columns:
            return
        self._columns = columns
        for column in range(3):
            self.card_grid.grid_columnconfigure(
                column, weight=1 if column < columns else 0, uniform="home-card"
            )
        for index, card in enumerate(self.cards.values()):
            card.grid(
                row=index // columns,
                column=index % columns,
                sticky="nsew",
                padx=6,
                pady=6,
            )

    def apply_state(self, state: WorkspaceHomeState):
        self.state = state
        selected = state.selected_device or "No device selected"
        serial = state.selected_serial or ""
        self.cards["Console"].set_state("Ready")
        self.cards["Instrumentation"].set_state(selected)
        self.cards["Device Recovery"].set_state(serial or "No device selected")
        self.cards["Script Studio"].set_state(
            state.selected_script or "Library ready"
        )
        self.cards["Pentest"].set_state(
            state.active_assessment or "No active assessment"
        )
        count = max(0, int(state.active_sessions))
        self.cards["Sessions"].set_state(
            f"{count} active session{'s' if count != 1 else ''}"
        )
        advanced = state.interface_mode == "advanced"
        descriptions = (
            self.ADVANCED_DESCRIPTIONS if advanced else self.GUIDED_DESCRIPTIONS
        )
        for title, card in self.cards.items():
            card.set_description(descriptions[title])
        if advanced:
            target = state.selected_target or "No target selected"
            self.recommendation.configure(
                text=(
                    f"Current selection: {serial or 'No serial'} · {target}. "
                    "Open a workspace for technical controls."
                )
            )
        else:
            self.recommendation.configure(
                text=(
                    "Recommended next step: "
                    + (
                        "open Instrumentation or Device Recovery for the selected device."
                        if serial else
                        "select a device, or open Console to work locally."
                    )
                )
            )

    def focus_first_card(self):
        first = next(iter(self.cards.values()), None)
        if first is not None:
            first.open_button.focus_set()
