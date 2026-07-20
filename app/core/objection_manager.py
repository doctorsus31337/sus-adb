"""Objection command construction, readiness checks, and terminal launch."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable, Sequence

from app.core.command_result import CommandResult
from app.core.command_runner import CommandRunner
from app.core.external_terminal import ExternalTerminal
from app.core.frida_manager import FridaManager
from app.core.host_tool_resolver import HostToolResolver


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
        resolver: HostToolResolver | None = None,
    ):
        self.runner = runner
        self.frida = frida
        self.terminal = terminal
        self._objection_explicit = objection_path is not None
        self.resolver = resolver or HostToolResolver(**({"which": which} if which else {}))
        self.objection_path = self.resolver.resolve("objection") if objection_path is None else objection_path

    def version(self) -> CommandResult:
        executable = self.objection_path if self._objection_explicit else self.resolver.resolve("objection")
        if not executable:
            return CommandResult.from_command(
                ("objection", "version"), -1,
                error=self.resolver.missing_message("objection", "Objection"),
            )
        self.objection_path = executable
        return self.runner.run((executable, "version"), timeout=10)

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
        if not self.objection_path and not self._objection_explicit:
            self.objection_path = self.resolver.resolve("objection")
        installed = bool(self.objection_path)
        device_available = bool(serial)
        target_valid = self.validate_target(target).ok
        normalized = transport.strip().casefold()
        forwarding_ready = True
        reachable = False

        if not installed:
            errors.append(self.resolver.missing_message("objection", "Objection"))
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
