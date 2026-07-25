"""Lightweight, responsive landing workspace for SUS Companion."""

from __future__ import annotations

import textwrap

import customtkinter as ctk

from app.core.workspace_navigation import WorkspaceHomeState


class WorkspaceHomeCard(ctk.CTkButton):
    def __init__(self, parent, theme, mark, title, description, command):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            hover_color=theme["panel_alt"],
            text_color=theme["text"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=12,
            height=166,
            anchor="w",
            font=("Segoe UI", 13),
            command=command,
        )
        self.theme = theme
        self.command = command
        self.mark = mark
        self.title_text = title
        self.description = description
        self.state = "Ready"
        self.open_button = self
        self._canvas.configure(takefocus=True)
        self.bind("<Return>", lambda _event: self._activate())
        self.bind("<space>", lambda _event: self._activate())
        self._render_body()

    def _activate(self):
        self.command()
        return "break"

    def set_state(self, text):
        self.state = text or "Ready"
        self._render_body()

    def set_description(self, text):
        self.description = text
        self._render_body()

    def _render_body(self):
        description = textwrap.fill(self.description, width=38)
        state = textwrap.fill(self.state, width=38)
        self.configure(
            text=(
                f"{self.mark}  {self.title_text}\n\n"
                f"{description}\n\n{state}\n\nOPEN →"
            )
        )


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
        self._explore_actions = tuple(explore_actions)
        self.state = WorkspaceHomeState()
        self.cards = {}
        self._columns = 0
        self._explore_columns = 0
        self._content_after_id = None
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.scroll = None
        self.card_grid = None
        self.explore = None
        self.explore_heading = None
        self.explore_bar = None
        self.explore_buttons = []
        self.heading = ctk.CTkLabel(
            self,
            text="Workspace Home",
            text_color=theme["gold"],
            font=("Times New Roman", 28, "bold"),
            anchor="w",
        )
        self.heading.grid(row=0, column=0, sticky="ew", padx=16, pady=(13, 1))
        self.intro = ctk.CTkLabel(
            self,
            text="Choose one workspace. Nothing scans or executes from this screen.",
            text_color=theme["muted"],
            anchor="w",
        )
        self.intro.grid(row=1, column=0, sticky="ew", padx=16, pady=(1, 8))
        self.recommendation = ctk.CTkLabel(
            self,
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
        self._content_after_id = self.after(750, self.ensure_content)

    def ensure_content(self):
        if self.cards:
            return
        self._content_after_id = None
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=self.theme["bg"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.scroll.grid(row=3, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.card_grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.card_grid.grid(row=0, column=0, sticky="ew", padx=10)
        self.explore = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.explore.grid(row=1, column=0, sticky="ew", padx=16, pady=(13, 16))
        self.explore.grid_columnconfigure(0, weight=1)
        self.explore_heading = ctk.CTkLabel(
            self.explore,
            text="Explore",
            text_color=self.theme["gold"],
            font=("Times New Roman", 18, "bold"),
            anchor="w",
        )
        self.explore_heading.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.explore_bar = ctk.CTkFrame(
            self.explore, fg_color="transparent"
        )
        self.explore_bar.grid(row=1, column=0, sticky="ew")
        for title, mark, description in self.CARD_SPECS:
            self.cards[title] = WorkspaceHomeCard(
                self.card_grid,
                self.theme,
                mark,
                title,
                description,
                self.actions[title],
            )
        self._build_explore_actions()
        self.card_grid.bind("<Configure>", self._layout_cards, add="+")
        self.explore_bar.bind("<Configure>", self._layout_explore, add="+")
        self._layout_cards()
        self._layout_explore()
        self.apply_state(self.state)

    def _build_explore_actions(self):
        if self.explore_buttons:
            return
        for column, (title, command) in enumerate(self._explore_actions):
            self.explore_bar.grid_columnconfigure(column, weight=1)
            button = ctk.CTkButton(
                self.explore_bar,
                text=title,
                command=command,
                height=31,
                fg_color=self.theme["panel_alt"],
                hover_color=self.theme["gold_dark"],
                text_color=self.theme["text"],
                border_width=1,
                border_color=self.theme["gold_dark"],
            )
            button.grid(row=0, column=column, sticky="ew", padx=3)
            button._canvas.configure(takefocus=True)
            self.explore_buttons.append(button)

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

    def _layout_explore(self, _event=None):
        width = max(1, self.explore_bar.winfo_width())
        columns = 5 if width >= 1120 else 3 if width >= 700 else 2
        if columns == self._explore_columns:
            return
        self._explore_columns = columns
        for column in range(5):
            self.explore_bar.grid_columnconfigure(
                column, weight=1 if column < columns else 0
            )
        for index, button in enumerate(self.explore_buttons):
            button.grid(
                row=index // columns,
                column=index % columns,
                sticky="ew",
                padx=3,
                pady=3,
            )

    def apply_state(self, state: WorkspaceHomeState):
        self.state = state
        advanced = state.interface_mode == "advanced"
        if advanced:
            target = state.selected_target or "No target selected"
            self.recommendation.configure(
                text=(
                    f"Current selection: {state.selected_serial or 'No serial'} "
                    f"· {target}. Open a workspace for technical controls."
                )
            )
        else:
            self.recommendation.configure(
                text=(
                    "Recommended next step: "
                    + (
                        "open Instrumentation or Device Recovery for the selected device."
                        if state.selected_serial else
                        "select a device, or open Console to work locally."
                    )
                )
            )
        if not self.cards:
            return
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
        descriptions = (
            self.ADVANCED_DESCRIPTIONS if advanced else self.GUIDED_DESCRIPTIONS
        )
        for title, card in self.cards.items():
            card.set_description(descriptions[title])

    def focus_first_card(self):
        first = next(iter(self.cards.values()), None)
        if first is not None:
            first.open_button.focus_set()
        else:
            self.heading._canvas.configure(takefocus=True)
            self.heading.focus_set()

    def destroy(self):
        if self._content_after_id is not None:
            self.after_cancel(self._content_after_id)
            self._content_after_id = None
        super().destroy()
