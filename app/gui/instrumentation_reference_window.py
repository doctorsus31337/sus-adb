"""Non-modal searchable Frida and Objection advanced command reference."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from app.core.frida_target import FridaTarget
from app.core.instrumentation_reference import (
    FRIDA_REPL_STARTER,
    OBJECTION_REPL_STARTER,
    ReferenceCommand,
    expand_reference_command,
    filter_reference_commands,
    reference_categories,
    reference_commands,
)


class InstrumentationReferenceWindow(ctk.CTkToplevel):
    WIDTH = 620
    HEIGHT = 650

    def __init__(
        self,
        parent,
        theme,
        target_provider: Callable[[], FridaTarget | None],
        copy_callback: Callable[[str], None] | None = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.theme = theme
        self.target_provider = target_provider
        self.copy_callback = copy_callback
        self.title("Frida / Objection Advanced Command Reference")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(560, 540)
        self.configure(fg_color=theme["bg"])
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_filters()
        self._build_starters()
        self._build_commands()
        self._build_footer()
        self.after_idle(self._place_relative_to_main)
        self.after_idle(self.refresh_commands)

    def _build_header(self):
        ctk.CTkLabel(
            self, text="⚔ FRIDA / OBJECTION ADVANCED COMMAND REFERENCE ⚔",
            text_color=self.theme["gold"], font=("Times New Roman", 22, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 5))

    def _build_filters(self):
        toolbar = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["border"], corner_radius=8,
        )
        toolbar.grid(row=1, column=0, sticky="ew", padx=12, pady=5)
        toolbar.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(
            toolbar, placeholder_text="Search commands and explanations...",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"], placeholder_text_color=self.theme["muted"],
        )
        self.search_entry.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 5))
        self.search_entry.bind("<KeyRelease>", lambda _event: self.refresh_commands())
        self.tool_filter = ctk.CTkSegmentedButton(
            toolbar, values=["All", "Frida CLI", "Frida REPL", "Objection REPL"],
            command=lambda _value: self._filter_changed(),
            selected_color=self.theme["red"], selected_hover_color=self.theme["red_hover"],
            unselected_color=self.theme["panel_alt"],
            unselected_hover_color=self.theme["gold_dark"], text_color=self.theme["text"],
        )
        self.tool_filter.grid(row=1, column=0, sticky="w", padx=8, pady=(4, 8))
        self.tool_filter.set("All")
        self.category_filter = ctk.CTkComboBox(
            toolbar, values=["All", *reference_categories()], state="readonly",
            command=lambda _value: self.refresh_commands(),
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            button_color=self.theme["red"], button_hover_color=self.theme["red_hover"],
            dropdown_fg_color=self.theme["panel_alt"],
            dropdown_hover_color=self.theme["red"],
            text_color=self.theme["text"], dropdown_text_color=self.theme["text"],
        )
        self.category_filter.grid(row=1, column=1, sticky="e", padx=8, pady=(4, 8))
        self.category_filter.set("All")

    def _build_starters(self):
        starter = ctk.CTkFrame(
            self, fg_color=self.theme["panel_alt"], border_width=1,
            border_color=self.theme["gold_dark"], corner_radius=8,
        )
        starter.grid(row=2, column=0, sticky="ew", padx=12, pady=5)
        starter.grid_columnconfigure(0, weight=1)
        self.starter_label = ctk.CTkLabel(
            starter, text=self._starter_text(), text_color=self.theme["text"],
            font=("Consolas", 11), justify="left", anchor="w", wraplength=470,
        )
        self.starter_label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        self.copy_starter_button = ctk.CTkButton(
            starter, text="Copy Starter Sequence", command=self.copy_starter_sequence,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"], width=155,
        )
        self.copy_starter_button.grid(row=0, column=1, padx=10, pady=8)

    def _build_commands(self):
        self.command_list = ctk.CTkScrollableFrame(
            self, fg_color=self.theme["terminal_bg"], border_width=1,
            border_color=self.theme["border"], corner_radius=8,
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.command_list.grid(row=3, column=0, sticky="nsew", padx=12, pady=5)
        self.command_list.grid_columnconfigure(0, weight=1)

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=12, pady=(3, 10))
        footer.grid_columnconfigure(0, weight=1)
        self.result_count = ctk.CTkLabel(
            footer, text="", text_color=self.theme["gold"], font=("Segoe UI", 12, "bold"),
        )
        self.result_count.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer, text="Close", command=self.destroy, fg_color=self.theme["panel_alt"],
            hover_color=self.theme["red"], text_color=self.theme["text"],
            border_width=1, border_color=self.theme["gold_dark"], width=90,
        ).grid(row=0, column=1, sticky="e")

    def refresh_commands(self):
        for widget in self.command_list.winfo_children():
            widget.destroy()
        commands = filter_reference_commands(
            reference_commands(), query=self.search_entry.get(),
            tool=self.tool_filter.get(), category=self.category_filter.get(),
        )
        self.result_count.configure(text=f"{len(commands)} command{'s' if len(commands) != 1 else ''}")
        if not commands:
            ctk.CTkLabel(
                self.command_list, text="No matching commands.", text_color=self.theme["muted"],
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=20)
            return
        for row, command in enumerate(commands):
            self._command_card(command).grid(row=row, column=0, sticky="ew", padx=3, pady=4)

    def _command_card(self, command: ReferenceCommand):
        expanded = expand_reference_command(command, self.target_provider())
        card = ctk.CTkFrame(
            self.command_list, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["border"], corner_radius=8,
        )
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text=f"{command.tool}  ·  {command.category}",
            text_color=self.theme["gold"], font=("Segoe UI", 12, "bold"), anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        badge_color = self.theme["red"] if command.changes_runtime else self.theme["gold_dark"]
        ctk.CTkLabel(
            card, text=command.classification, fg_color=badge_color,
            text_color=self.theme["text"], corner_radius=5, font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=1, padx=10, pady=(8, 2))
        ctk.CTkLabel(
            card, text=expanded.command, text_color=self.theme["terminal_text"],
            fg_color=self.theme["terminal_bg"], font=("Consolas", 12),
            anchor="w", justify="left", wraplength=500, corner_radius=5,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=4)
        ctk.CTkLabel(
            card, text=f"{command.description}\n{command.explanation}\nContext: {command.execution_context}",
            text_color=self.theme["text"], justify="left", anchor="w", wraplength=500,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=3)
        guidance = []
        if not expanded.ready:
            guidance.append(expanded.guidance)
        if command.caution:
            guidance.append(f"Caution: {command.caution}")
        if guidance:
            ctk.CTkLabel(
                card, text="\n".join(guidance), text_color=self.theme["error"],
                justify="left", anchor="w", wraplength=500,
            ).grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 8))
        ctk.CTkButton(
            card, text="Copy Command", command=lambda text=expanded.command: self.copy_text(text),
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"], width=110,
        ).grid(row=3, column=1, sticky="e", padx=10, pady=(2, 8))
        return card

    def _filter_changed(self):
        self.category_filter.set("All")
        self.starter_label.configure(text=self._starter_text())
        self.refresh_commands()

    def _starter_sequence(self) -> tuple[str, ...]:
        return OBJECTION_REPL_STARTER if self.tool_filter.get() == "Objection REPL" else FRIDA_REPL_STARTER

    def _starter_text(self) -> str:
        if hasattr(self, "tool_filter") and self.tool_filter.get() == "Objection REPL":
            return (
                "Objection starter (read-only inspection):\n"
                + "  ·  ".join(OBJECTION_REPL_STARTER)
            )
        return (
            "Frida starter (read-only inspection):\n"
            + "  ·  ".join(FRIDA_REPL_STARTER)
            + "\nUse Java.androidVersion only when Java.available returns true."
        )

    def copy_starter_sequence(self):
        self.copy_text("\n".join(self._starter_sequence()))

    def copy_text(self, text: str):
        if self.copy_callback is not None:
            self.copy_callback(text)
            return
        self.clipboard_clear()
        self.clipboard_append(text)

    def _place_relative_to_main(self):
        self.update_idletasks()
        main = self.parent.winfo_toplevel()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        right_x = main.winfo_rootx() + main.winfo_width() + 8
        left_x = main.winfo_rootx() - self.WIDTH - 8
        if right_x + self.WIDTH <= screen_w:
            x = right_x
        elif left_x >= 0:
            x = left_x
        else:
            x = max(0, main.winfo_rootx() + (main.winfo_width() - self.WIDTH) // 2)
        y = max(0, min(main.winfo_rooty() + 45, screen_h - self.HEIGHT - 40))
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
