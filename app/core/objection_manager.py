"""Objection command construction, readiness checks, and terminal launch."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from collections.abc import Callable, Sequence

from app.core.command_result import CommandResult
from app.core.command_runner import CommandRunner
from app.core.external_terminal import ExternalTerminal
from app.core.frida_manager import FridaManager


@dataclass(frozen=True, slots=True)
class ObjectionReadiness:
    ready: bool
    objection_installed: bool
    device_available: bool
    target_valid: bool
    frida_reachable: bool
    forwarding_ready: bool
    errors: tuple[str, ...] = field(default_factory=tuple)


class ObjectionManager:
    def __init__(
        self,
        runner: CommandRunner,
        frida: FridaManager,
        terminal: ExternalTerminal,
        *,
        objection_path: str | None = None,
        which: Callable[[str], str | None] | None = None,
    ):
        self.runner = runner
        self.frida = frida
        self.terminal = terminal
        self.which = which or shutil.which
        self.objection_path = self.which("objection") if objection_path is None else objection_path

    def version(self) -> CommandResult:
        if not self.objection_path:
            return CommandResult.from_command(
                ("objection", "version"), -1, error="Objection was not found in PATH."
            )
        return self.runner.run((self.objection_path, "version"), timeout=10)

    @staticmethod
    def validate_target(target: str) -> CommandResult:
        value = target.strip()
        if not value:
            return CommandResult.from_command(
                ("objection",), -1, error="An application or process target is required."
            )
        if "\x00" in value or "\r" in value or "\n" in value:
            return CommandResult.from_command(
                ("objection",), -1, error="The target contains unsupported control characters."
            )
        return CommandResult.from_command(("objection", value), 0, stdout=value)

    def build_attach_command(
        self, target: str, transport: str, serial: str | None = None
    ) -> tuple[str, ...]:
        return self._build_command(target, transport, serial, spawn=False)

    def build_spawn_command(
        self, target: str, transport: str, serial: str | None = None
    ) -> tuple[str, ...]:
        return self._build_command(target, transport, serial, spawn=True)

    def _build_command(
        self, target: str, transport: str, serial: str | None, *, spawn: bool
    ) -> tuple[str, ...]:
        validation = self.validate_target(target)
        if not validation.ok:
            raise ValueError(validation.error)
        normalized = transport.strip().casefold()
        if normalized not in {"socket", "usb"}:
            raise ValueError(f"Unsupported Objection transport: {transport}")
        device = "socket" if normalized == "socket" else (serial or "usb")
        command = [self.objection_path or "objection", "-S", device, "-n", target.strip()]
        if spawn:
            command.append("-s")
        command.append("start")
        return tuple(command)

    def readiness(self, serial: str | None, target: str, transport: str) -> ObjectionReadiness:
        errors: list[str] = []
        installed = bool(self.objection_path)
        device_available = bool(serial)
        target_valid = self.validate_target(target).ok
        normalized = transport.strip().casefold()
        forwarding_ready = True
        reachable = False

        if not installed:
            errors.append("Objection was not found in PATH.")
        if not device_available:
            errors.append("No device is selected.")
        if not target_valid:
            errors.append("An application or process target is required.")
        if normalized not in {"socket", "usb"}:
            errors.append(f"Unsupported Objection transport: {transport}")
        elif serial:
            diagnosis = self.frida.diagnose(serial)
            reachable = diagnosis.reachable
            if normalized == "socket":
                forwarding_ready = diagnosis.port_27042 and diagnosis.port_27043
                if not forwarding_ready:
                    errors.append("Socket transport requires TCP 27042 and 27043 forwarding.")
            if not reachable:
                errors.append("Frida is not reachable on the selected device.")
        else:
            forwarding_ready = normalized != "socket"

        return ObjectionReadiness(
            not errors, installed, device_available, target_valid, reachable,
            forwarding_ready, tuple(errors),
        )

    def launch_external_session(self, command: Sequence[str]) -> CommandResult:
        return self.terminal.launch(command)
