"""Objection command construction, readiness checks, and terminal launch."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable, Sequence

from app.core.command_result import CommandResult
from app.core.command_runner import CommandRunner
from app.core.external_terminal import ExternalTerminal
from app.core.frida_manager import FridaManager
from app.core.host_tool_resolver import HostToolResolver
from app.core.instrumentation_launch import is_application_identifier, normalize_transport


DEFAULT_OBJECTION_HOST = "127.0.0.1"
DEFAULT_OBJECTION_PORT = 27042


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
    def validate_target(target: str, *, spawn: bool = False) -> CommandResult:
        value = target.strip()
        if not value:
            return CommandResult.from_command(
                ("objection",), -1, error="An application or process target is required."
            )
        if "\x00" in value or "\r" in value or "\n" in value:
            return CommandResult.from_command(
                ("objection",), -1, error="The target contains unsupported control characters."
            )
        if value.isdecimal():
            message = (
                "Spawn requires a package/application identifier; a numeric PID is not supported."
                if spawn else
                "Objection attach requires an application identifier or process name; a PID is not supported."
            )
            return CommandResult.from_command(
                ("objection", value), -1, error=message,
            )
        if spawn and not is_application_identifier(value):
            return CommandResult.from_command(
                ("objection", value), -1,
                error="Spawn requires a package/application identifier such as com.example.app.",
            )
        return CommandResult.from_command(("objection", value), 0, stdout=value)

    def build_attach_command(
        self, target: str, transport: str, serial: str | None = None,
        *, host: str = DEFAULT_OBJECTION_HOST, port: int | str = DEFAULT_OBJECTION_PORT,
    ) -> tuple[str, ...]:
        return self._build_command(
            target, transport, serial, host=host, port=port, spawn=False
        )

    def build_spawn_command(
        self, target: str, transport: str, serial: str | None = None,
        *, host: str = DEFAULT_OBJECTION_HOST, port: int | str = DEFAULT_OBJECTION_PORT,
    ) -> tuple[str, ...]:
        return self._build_command(
            target, transport, serial, host=host, port=port, spawn=True
        )

    def _build_command(
        self, target: str, transport: str, serial: str | None, *,
        host: str, port: int | str, spawn: bool,
    ) -> tuple[str, ...]:
        validation = self.validate_target(target, spawn=spawn)
        if not validation.ok:
            raise ValueError(validation.error)
        normalized = normalize_transport(transport)
        if normalized not in {"network", "usb"}:
            raise ValueError(f"Unsupported Objection transport: {transport}")
        command = [self.objection_path or "objection"]
        if normalized == "usb":
            selected_serial = self._validate_route_value(serial, "USB serial")
            command.extend(("-S", selected_serial))
        else:
            network_host = self._validate_route_value(host, "Network host")
            network_port = self._validate_port(port)
            command.extend(("-N", "-h", network_host, "-P", str(network_port)))
        command.extend(("-n", target.strip()))
        if spawn:
            command.append("-s")
        command.append("start")
        return tuple(command)

    def readiness(
        self, serial: str | None, target: str, transport: str, *,
        spawn: bool = False, host: str = DEFAULT_OBJECTION_HOST,
        port: int | str = DEFAULT_OBJECTION_PORT,
    ) -> ObjectionReadiness:
        errors: list[str] = []
        if not self.objection_path and not self._objection_explicit:
            self.objection_path = self.resolver.resolve("objection")
        installed = bool(self.objection_path)
        device_available = bool(serial)
        target_result = self.validate_target(target, spawn=spawn)
        target_valid = target_result.ok
        normalized = normalize_transport(transport)
        forwarding_ready = True
        reachable = False

        if not installed:
            errors.append(self.resolver.missing_message("objection", "Objection"))
        if not device_available:
            errors.append("No device is selected.")
        if not target_valid:
            errors.append(target_result.error)
        route_valid = normalized in {"network", "usb"}
        if not route_valid:
            errors.append(f"Unsupported Objection transport: {transport}")
        elif normalized == "usb":
            try:
                self._validate_route_value(serial, "USB serial")
            except ValueError as exc:
                errors.append(str(exc))
        else:
            try:
                self._validate_route_value(host, "Network host")
                self._validate_port(port)
            except ValueError as exc:
                errors.append(str(exc))
        if route_valid and serial:
            diagnosis = self.frida.diagnose(serial)
            reachable = diagnosis.reachable
            if normalized == "network":
                forwarding_ready = diagnosis.port_27042 and diagnosis.port_27043
                if not forwarding_ready:
                    errors.append("Network transport requires TCP 27042 and 27043 forwarding.")
            if not reachable:
                errors.append("Frida is not reachable on the selected device.")
        elif route_valid:
            forwarding_ready = normalized != "network"

        return ObjectionReadiness(
            not errors, installed, device_available, target_valid, reachable,
            forwarding_ready, tuple(errors),
        )

    def launch_external_session(self, command: Sequence[str]) -> CommandResult:
        return self.terminal.launch(command)

    @staticmethod
    def _validate_route_value(value: str | None, label: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{label} is required.")
        if any(character.isspace() or character == "\x00" for character in normalized):
            raise ValueError(f"{label} must not contain whitespace or control characters.")
        return normalized

    @staticmethod
    def _validate_port(value: int | str) -> int:
        try:
            port = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Network port must be a number from 1 to 65535.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Network port must be from 1 to 65535.")
        return port
