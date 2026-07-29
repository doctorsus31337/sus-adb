"""Finite, GUI-neutral policy for integrated Fastboot commands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class FastbootCommandKind(str, Enum):
    VERSION = "version"
    HELP = "help"
    DEVICES = "devices"
    DEVICES_LONG = "devices-long"
    GETVAR = "getvar"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class FastbootCommandParseResult:
    kind: FastbootCommandKind
    serial: str = ""
    variable: str = ""
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.kind is not FastbootCommandKind.UNSUPPORTED


class FastbootCommandPolicy:
    """Accept only the explicitly reviewed read-only Fastboot grammar."""

    MAX_SERIAL_LENGTH = 128
    MAX_VARIABLE_LENGTH = 64
    _VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
    _SHELL_METACHARACTERS = frozenset(";&|`$<>(){}[]!*?~")
    _BLOCKED_MESSAGE = (
        "This Fastboot operation is not supported in the integrated Console. "
        "Destructive bootloader operations belong in the guided Root & Boot "
        "Integrity or Firmware Recovery workflow."
    )

    @classmethod
    def parse(cls, argv: Sequence[str]) -> FastbootCommandParseResult:
        values = tuple(str(value) for value in argv)
        arguments = values[1:]
        unsafe = next((value for value in arguments if cls._unsafe(value)), "")
        if unsafe:
            return cls._blocked("Shell metacharacters and control characters are not accepted.")
        if sum(value in {"-s", "--serial"} for value in arguments) > 1:
            return cls._blocked("Specify exactly one Fastboot serial option.")
        if arguments == ("--version",):
            return FastbootCommandParseResult(FastbootCommandKind.VERSION)
        if arguments == ("help",):
            return FastbootCommandParseResult(FastbootCommandKind.HELP)
        if arguments == ("devices",):
            return FastbootCommandParseResult(FastbootCommandKind.DEVICES)
        if arguments == ("devices", "-l"):
            return FastbootCommandParseResult(FastbootCommandKind.DEVICES_LONG)
        if arguments and arguments[0] == "getvar":
            return cls._blocked("Fastboot getvar requires an explicit -s or --serial value.")
        if arguments and arguments[0] in {"-s", "--serial"}:
            if len(arguments) < 2 or not arguments[1]:
                return cls._blocked("Fastboot -s/--serial requires a non-empty serial.")
            serial_error = cls._value_error(
                arguments[1], "Fastboot serial", cls.MAX_SERIAL_LENGTH
            )
            if serial_error:
                return cls._blocked(serial_error)
            if len(arguments) < 3 or arguments[2] != "getvar":
                return cls._blocked(
                    "An explicit Fastboot serial may only be used with getvar."
                )
            if len(arguments) < 4 or not arguments[3]:
                return cls._blocked("Fastboot getvar requires one variable.")
            variable_error = cls._value_error(
                arguments[3], "Fastboot variable", cls.MAX_VARIABLE_LENGTH
            )
            if variable_error:
                return cls._blocked(variable_error)
            if len(arguments) != 4:
                return cls._blocked("Fastboot getvar accepts exactly one variable.")
            return FastbootCommandParseResult(
                FastbootCommandKind.GETVAR,
                serial=arguments[1],
                variable=arguments[3],
            )
        if any(value in {"--force", "-w"} for value in arguments):
            return cls._blocked("Force and wipe options are never accepted here.")
        if any(value.startswith("-") for value in arguments):
            return cls._blocked("Unsupported Fastboot global option.")
        return cls._blocked("The command does not match the reviewed read-only grammar.")

    @classmethod
    def _value_error(cls, value: str, label: str, maximum: int) -> str:
        if not value:
            return f"{label} cannot be empty."
        if len(value) > maximum:
            return f"{label} exceeds the {maximum}-character limit."
        if value.startswith(("-", "/")):
            return f"{label} cannot begin with an option prefix."
        if "/" in value or "\\" in value or value in {".", ".."}:
            return f"{label} cannot be path-like."
        if cls._unsafe(value) or cls._VALUE.fullmatch(value) is None:
            return f"{label} contains unsupported characters."
        return ""

    @classmethod
    def _unsafe(cls, value: str) -> bool:
        return any(
            ord(character) < 32
            or ord(character) == 127
            or character in cls._SHELL_METACHARACTERS
            for character in value
        )

    @classmethod
    def _blocked(cls, detail: str) -> FastbootCommandParseResult:
        return FastbootCommandParseResult(
            FastbootCommandKind.UNSUPPORTED,
            reason=f"{cls._BLOCKED_MESSAGE} {detail}",
        )
