"""Parsed-argv command classification for one-shot versus interactive execution."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.core.command_registry import CommandRegistry


class CommandClassification(str, Enum):
    ONE_SHOT = "one-shot"
    INTERACTIVE = "interactive"
    STREAMING_FINITE = "streaming-but-finite"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class CommandRoute:
    raw: str
    argv: tuple[str, ...]
    resolved_argv: tuple[str, ...]
    classification: CommandClassification
    session_type: str = ""
    serial: str = ""
    target: str = ""
    reason: str = ""

    @property
    def opens_session(self) -> bool:
        return self.classification is CommandClassification.INTERACTIVE


class CommandRouter:
    HOST_SHELLS = frozenset(("bash", "zsh", "sh", "fish", "pwsh", "powershell", "cmd"))
    VERSION_FLAGS = frozenset(("--help", "-h", "--version", "-V", "version"))

    def __init__(self, resolver=None, *, platform_name: str | None = None):
        self.resolver = resolver
        self.platform_name = platform_name or os.name
        self.registry_executables = frozenset(
            self._name(shlex.split(command, posix=True)[0])
            for command in CommandRegistry.all_commands()
            if command.strip()
        )

    @staticmethod
    def _name(value: str) -> str:
        name = Path(value.replace("\\", "/")).name.casefold()
        return name[:-4] if name.endswith(".exe") else name

    def classify(self, command: str) -> CommandRoute:
        raw = command.strip()
        try:
            argv = tuple(shlex.split(raw, posix=self.platform_name != "nt"))
        except ValueError as exc:
            return CommandRoute(raw, (), (), CommandClassification.UNSUPPORTED, reason=f"Could not parse command: {exc}")
        if not argv:
            return CommandRoute(raw, (), (), CommandClassification.UNSUPPORTED, reason="No command was provided.")
        resolved = argv
        if self.resolver is not None:
            executable = self.resolver.resolve(argv[0])
            if executable:
                resolved = (executable, *argv[1:])
        name = self._name(argv[0])
        if name == "adb":
            return self._adb(raw, argv, resolved)
        if name == "objection":
            return self._objection(raw, argv, resolved)
        if name == "frida-ps":
            return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT, reason="Frida process discovery is finite.")
        if name == "frida":
            if any(value in self.VERSION_FLAGS for value in argv[1:]):
                return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT)
            return CommandRoute(raw, argv, resolved, CommandClassification.INTERACTIVE, "frida-repl", target=self._frida_target(argv), reason="Frida opens an interactive REPL.")
        if name == "frida-trace":
            if any(value in self.VERSION_FLAGS for value in argv[1:]):
                return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT)
            return CommandRoute(raw, argv, resolved, CommandClassification.INTERACTIVE, "frida-trace", target=self._frida_target(argv), reason="Frida Trace remains attached until interrupted.")
        if name in self.HOST_SHELLS:
            finite = "-c" in argv[1:] or "/c" in {value.casefold() for value in argv[1:]}
            return CommandRoute(
                raw, argv, resolved,
                CommandClassification.ONE_SHOT if finite else CommandClassification.INTERACTIVE,
                "host-shell" if not finite else "",
                reason="Host shells require a terminal." if not finite else "",
            )
        if name in {"help", "clear", "cls", "stop", "cd"}:
            return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT)
        if name in self.registry_executables:
            return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT)
        return CommandRoute(
            raw, argv, resolved, CommandClassification.AMBIGUOUS,
            reason="This command is not in the supported command registry. Use a dedicated terminal for unclassified commands.",
        )

    def _adb(self, raw, argv, resolved):
        command_index = 1
        serial = ""
        while command_index < len(argv):
            value = argv[command_index]
            if value in {"-s", "--serial"}:
                if command_index + 1 >= len(argv):
                    return CommandRoute(raw, argv, resolved, CommandClassification.UNSUPPORTED, reason="ADB -s requires a serial.")
                serial = argv[command_index + 1]
                command_index += 2
                continue
            if value in {"-d", "-e", "-a"}:
                command_index += 1
                continue
            if value.startswith("-"):
                command_index += 1
                continue
            break
        subcommand = argv[command_index].casefold() if command_index < len(argv) else ""
        trailing = argv[command_index + 1:]
        if subcommand == "shell" and not trailing:
            return CommandRoute(raw, argv, resolved, CommandClassification.INTERACTIVE, "adb-shell", serial=serial, reason="ADB Shell opens an interactive device session.")
        if subcommand == "logcat" and "-d" not in trailing:
            return CommandRoute(raw, argv, resolved, CommandClassification.INTERACTIVE, "adb-logcat", serial=serial, reason="Live Logcat is an open-ended streaming session.")
        if subcommand in {"pull", "push", "install", "install-multiple", "bugreport"} or subcommand == "logcat" and "-d" in trailing:
            return CommandRoute(raw, argv, resolved, CommandClassification.STREAMING_FINITE, serial=serial)
        return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT, serial=serial)

    @staticmethod
    def _objection(raw, argv, resolved):
        target = ""
        for index, value in enumerate(argv[:-1]):
            if value in {"-n", "--name"}:
                target = argv[index + 1]
        if "start" in {value.casefold() for value in argv[1:]}:
            return CommandRoute(raw, argv, resolved, CommandClassification.INTERACTIVE, "objection", target=target, reason="Objection start opens an interactive prompt.")
        return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT, target=target)

    @staticmethod
    def _frida_target(argv):
        for index, value in enumerate(argv[:-1]):
            if value in {"-n", "-N", "-f", "-p"}:
                return argv[index + 1]
        return ""
