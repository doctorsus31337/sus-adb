"""Reusable cross-platform external terminal launching."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Sequence

from app.core.command_result import CommandResult


class ExternalTerminal:
    LINUX_TERMINALS = (
        "x-terminal-emulator", "konsole", "gnome-terminal",
        "xfce4-terminal", "kitty", "alacritty",
    )

    def __init__(
        self,
        *,
        which: Callable[[str], str | None] | None = None,
        launcher: Callable[..., object] | None = None,
        platform_name: str | None = None,
    ):
        self.which = which or shutil.which
        self.launcher = launcher or subprocess.Popen
        self.platform_name = platform_name or os.name

    def launch(self, command: Sequence[str]) -> CommandResult:
        args = tuple(str(part) for part in command)
        if not args:
            return CommandResult.from_command(args, -1, error="No external command was provided.")
        built = self.build_command(args)
        if not built.ok:
            return built
        try:
            self.launcher(built.command)
        except Exception as exc:
            return CommandResult.from_command(built.command, -1, error=str(exc))
        return CommandResult.from_command(
            built.command, 0, stdout="External terminal launched."
        )

    def build_command(self, command: Sequence[str]) -> CommandResult:
        args = tuple(str(part) for part in command)
        if not args:
            return CommandResult.from_command(args, -1, error="No external command was provided.")
        if self.platform_name == "nt":
            powershell = self.which("powershell") or self.which("powershell.exe")
            if not powershell:
                return CommandResult.from_command(args, -1, error="PowerShell was not found.")
            script = "& " + " ".join(self._powershell_quote(part) for part in args)
            return CommandResult.from_command((powershell, "-NoExit", "-Command", script), 0)

        terminal = None
        for candidate in self.LINUX_TERMINALS:
            terminal = self.which(candidate)
            if terminal:
                break
        if not terminal:
            return CommandResult.from_command(args, -1, error="No supported external terminal was found.")
        name = os.path.basename(terminal)
        separator = "--" if name == "gnome-terminal" else "-x" if name == "xfce4-terminal" else "-e"
        return CommandResult.from_command((terminal, separator, *args), 0)

    @staticmethod
    def _powershell_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"
