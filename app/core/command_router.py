"""Parsed-argv command classification for one-shot versus interactive execution."""

from __future__ import annotations

import ipaddress
import os
import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.core.fastboot_command import FastbootCommandPolicy
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
    fastboot_serial: str = ""
    target: str = ""
    reason: str = ""

    @property
    def opens_session(self) -> bool:
        return self.classification is CommandClassification.INTERACTIVE


class CommandRouter:
    HOST_SHELLS = frozenset(("bash", "zsh", "sh", "fish", "pwsh", "powershell", "cmd"))
    VERSION_FLAGS = frozenset(("--help", "-h", "--version", "-V", "version"))
    _ADB_ENDPOINT = re.compile(
        r"(?=.{3,255}\Z)(?!-)(?!.*\.\.)"
        r"(?:[A-Za-z0-9][A-Za-z0-9.-]*):([0-9]{1,5})\Z"
    )

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
        name = self._name(argv[0])
        resolved = argv
        if self.resolver is not None:
            executable = self.resolver.resolve(name)
            if executable:
                resolved = (executable, *argv[1:])
        if name == "fastboot":
            return self._fastboot(raw, argv, resolved)
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

    @staticmethod
    def _fastboot(raw, argv, resolved):
        parsed = FastbootCommandPolicy.parse(argv)
        if not parsed.allowed:
            return CommandRoute(
                raw, argv, resolved, CommandClassification.UNSUPPORTED,
                reason=parsed.reason,
            )
        return CommandRoute(
            raw, argv, resolved, CommandClassification.ONE_SHOT,
            fastboot_serial=parsed.serial,
            reason="Fastboot command matches the reviewed read-only grammar.",
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
        if subcommand == "pair":
            return CommandRoute(
                raw, argv, resolved, CommandClassification.UNSUPPORTED,
                reason=(
                    "ADB pairing is not supported in the integrated Console. "
                    "A future dedicated Wireless ADB pairing workflow will protect "
                    "interactive pairing codes from history and transcript capture."
                ),
            )
        if subcommand in {"version", "host-features", "features"}:
            if trailing:
                return CommandRoute(
                    raw, argv, resolved, CommandClassification.UNSUPPORTED,
                    reason=f"adb {subcommand} does not accept trailing arguments.",
                )
            return CommandRoute(
                raw, argv, resolved, CommandClassification.ONE_SHOT,
                serial=serial,
            )
        if subcommand == "mdns" and trailing == ("services",):
            return CommandRoute(
                raw, argv, resolved, CommandClassification.ONE_SHOT,
                serial=serial,
            )
        if subcommand == "connect":
            reason = self._adb_endpoint_reason(trailing)
            if reason:
                return CommandRoute(
                    raw, argv, resolved, CommandClassification.UNSUPPORTED,
                    reason=reason,
                )
            return CommandRoute(
                raw, argv, resolved, CommandClassification.ONE_SHOT,
                serial=serial,
            )
        if subcommand == "disconnect":
            reason = self._adb_endpoint_reason(trailing, optional=True)
            if reason:
                return CommandRoute(
                    raw, argv, resolved, CommandClassification.UNSUPPORTED,
                    reason=reason,
                )
            return CommandRoute(
                raw, argv, resolved, CommandClassification.ONE_SHOT,
                serial=serial,
            )
        if subcommand == "reconnect" and trailing in {("device",), ("offline",)}:
            return CommandRoute(
                raw, argv, resolved, CommandClassification.ONE_SHOT,
                serial=serial,
            )
        if subcommand == "shell" and not trailing:
            return CommandRoute(raw, argv, resolved, CommandClassification.INTERACTIVE, "adb-shell", serial=serial, reason="ADB Shell opens an interactive device session.")
        if subcommand == "logcat" and "-d" not in trailing:
            return CommandRoute(raw, argv, resolved, CommandClassification.INTERACTIVE, "adb-logcat", serial=serial, reason="Live Logcat is an open-ended streaming session.")
        if subcommand in {"pull", "push", "install", "install-multiple", "bugreport"} or subcommand == "logcat" and "-d" in trailing:
            return CommandRoute(raw, argv, resolved, CommandClassification.STREAMING_FINITE, serial=serial)
        return CommandRoute(raw, argv, resolved, CommandClassification.ONE_SHOT, serial=serial)

    @classmethod
    def _adb_endpoint_reason(cls, trailing, *, optional=False):
        if not trailing and optional:
            return ""
        if len(trailing) != 1:
            return "ADB connection commands require one explicit host:port endpoint."
        endpoint = trailing[0]
        if (
            any(
                ord(character) < 32
                or character in ";&|`$<>(){}[]!*?~\\/@"
                for character in endpoint
            )
            or "://" in endpoint
            or any(character.isspace() for character in endpoint)
        ):
            return (
                "ADB endpoint must not contain credentials, schemes, paths, "
                "whitespace, or shell controls."
            )
        match = cls._ADB_ENDPOINT.fullmatch(endpoint)
        if match is None:
            return (
                "ADB endpoint must be a bounded host or IPv4 address plus "
                "numeric port."
            )
        host = endpoint.rsplit(":", 1)[0]
        if all(character.isdigit() or character == "." for character in host):
            try:
                if ipaddress.ip_address(host).version != 4:
                    raise ValueError
            except ValueError:
                return "ADB endpoint contains an invalid IPv4 address."
        port = int(match.group(1))
        if not 1 <= port <= 65535:
            return "ADB endpoint port must be in the range 1–65535."
        return ""

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
