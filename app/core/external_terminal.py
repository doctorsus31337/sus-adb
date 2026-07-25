"""Reusable cross-platform external terminal launching."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from collections.abc import Callable, Sequence

from app.core.command_result import CommandResult


@dataclass(frozen=True, slots=True)
class ExternalLaunch:
    result: CommandResult
    process: object | None = None
    backend: str = ""


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
        realpath: Callable[[str], str] | None = None,
        configured_terminal: str | None = None,
    ):
        self.which = which or shutil.which
        self.launcher = launcher or subprocess.Popen
        self.platform_name = platform_name or os.name
        self.realpath = realpath or os.path.realpath
        self.configured_terminal = configured_terminal

    def launch(self, command: Sequence[str]) -> CommandResult:
        return self.launch_tracked(command).result

    def launch_tracked(self, command: Sequence[str], *, title: str = "SUS Companion Session") -> ExternalLaunch:
        args = tuple(str(part) for part in command)
        if not args:
            return ExternalLaunch(CommandResult.from_command(args, -1, error="No external command was provided."))
        built = self.build_command(args, title=title)
        if not built.ok:
            return ExternalLaunch(built)
        try:
            kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            if self.platform_name not in {"nt", "windows", "win32"}:
                kwargs["start_new_session"] = True
            process = self.launcher(built.command, **kwargs)
        except Exception as exc:
            return ExternalLaunch(CommandResult.from_command(built.command, -1, error=str(exc)))
        return ExternalLaunch(
            CommandResult.from_command(built.command, 0, stdout="External terminal launched."),
            process,
            self._backend_name(built.command[0]),
        )

    def build_command(self, command: Sequence[str], *, title: str = "SUS Companion Session") -> CommandResult:
        args = tuple(str(part) for part in command)
        if not args:
            return CommandResult.from_command(args, -1, error="No external command was provided.")
        if self.platform_name in {"nt", "windows", "win32"}:
            windows_terminal = self.which("wt.exe") or self.which("wt")
            if windows_terminal:
                return CommandResult.from_command(
                    (windows_terminal, "new-tab", "--title", title, *args), 0
                )
            powershell = (
                self.which("pwsh.exe") or self.which("pwsh")
                or self.which("powershell.exe") or self.which("powershell")
            )
            if powershell:
                script = "& " + " ".join(self._powershell_quote(part) for part in args)
                return CommandResult.from_command((powershell, "-NoExit", "-Command", script), 0)
            command_prompt = self.which("cmd.exe") or self.which("cmd")
            if command_prompt:
                return CommandResult.from_command(
                    (command_prompt, "/K", subprocess.list2cmdline(args)), 0
                )
            return CommandResult.from_command(args, -1, error="Windows Terminal, PowerShell, and cmd were not found.")

        terminal = self.configured_terminal
        for candidate in self.LINUX_TERMINALS:
            if terminal:
                break
            terminal = self.which(candidate)
            if terminal:
                break
        if not terminal:
            return CommandResult.from_command(args, -1, error="No supported external terminal was found.")
        resolved_name = os.path.basename(self.realpath(terminal)).casefold()
        if resolved_name in {"konsole", "konsole.exe"}:
            command = (terminal, "--separate", "--hold", "-e", *args)
        elif resolved_name == "gnome-terminal":
            command = (terminal, "--", *args)
        elif resolved_name == "xfce4-terminal":
            command = (terminal, "-x", *args)
        else:
            command = (terminal, "-e", *args)
        return CommandResult.from_command(command, 0)

    def _backend_name(self, executable: str) -> str:
        return os.path.basename(self.realpath(executable)).casefold()

    @staticmethod
    def _powershell_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"
