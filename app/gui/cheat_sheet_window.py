"""Non-modal floating command reference."""

import customtkinter as ctk

from app.core.command_registry import CommandRegistry
from app.core.app_metadata import METADATA


class CheatSheetWindow(ctk.CTkToplevel):
    WIDTH = 430
    HEIGHT = 560

    def __init__(self, parent, theme):
        super().__init__(parent)
        self.parent = parent
        self.theme = theme

        self.title(f"{METADATA.application_name} Quick Commands")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=theme["bg"])
        self.transient(parent)

        title = ctk.CTkLabel(
            self,
            text="⚔ QUICK COMMAND GRIMOIRE ⚔",
            font=("Times New Roman", 20, "bold"),
            text_color=theme["gold"],
        )
        title.pack(fill="x", padx=12, pady=(12, 8))

        console = ctk.CTkTextbox(
            self,
            fg_color=theme["terminal_bg"],
            text_color=theme["terminal_text"],
            font=("Consolas", 12),
            border_width=1,
            border_color=theme["border"],
            wrap="none",
        )
        console.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        console.insert("1.0", CommandRegistry.render_text())
        console.configure(state="disabled")

        self.after_idle(self._place_beside_parent)
        self.lift()

    def _place_beside_parent(self):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_w = self.parent.winfo_width()

        right_x = parent_x + parent_w + 10
        left_x = parent_x - self.WIDTH - 10

        if right_x + self.WIDTH <= screen_w:
            x = right_x
        elif left_x >= 0:
            x = left_x
        else:
            x = max(0, screen_w - self.WIDTH - 20)

        y = max(0, min(parent_y + 70, screen_h - self.HEIGHT - 50))
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
