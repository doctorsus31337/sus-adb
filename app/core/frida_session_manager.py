"""Frida command construction, readiness, previews, and external sessions."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from collections.abc import Sequence

from app.core.command_result import CommandResult
from app.core.external_terminal import ExternalTerminal
from app.core.frida_manager import FridaManager
from app.core.frida_target import FridaTarget


@dataclass(frozen=True, slots=True)
class FridaSessionReadiness:
    ready: bool
    warning: str | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    host_version: str | None = None
    server_version: str | None = None


class FridaSessionManager:
    ENDPOINT = "127.0.0.1:27042"

    def __init__(
        self,
        frida: FridaManager,
        terminal: ExternalTerminal,
        *,
        frida_path: str | None = None,
        frida_trace_path: str | None = None,
    ):
        self.frida = frida
        self.terminal = terminal
        self.frida_path = shutil.which("frida") if frida_path is None else frida_path
        self.frida_trace_path = shutil.which("frida-trace") if frida_trace_path is None else frida_trace_path

    def build_attach_command(self, target: FridaTarget | None) -> tuple[str, ...]:
        value = self._target_name(target)
        return (self.frida_path or "frida", "-H", self.ENDPOINT, "-n", value)

    def build_pid_command(self, target: FridaTarget | None) -> tuple[str, ...]:
        if target is None or target.pid is None or target.pid <= 0:
            raise ValueError("A valid target PID is required.")
        return (self.frida_path or "frida", "-H", self.ENDPOINT, "-p", str(target.pid))

    def build_spawn_command(self, target: FridaTarget | None) -> tuple[str, ...]:
        if target is None or not target.application_identifier:
            raise ValueError("An application identifier is required for spawn.")
        return (
            self.frida_path or "frida", "-H", self.ENDPOINT,
            "-f", target.application_identifier,
        )

    def build_repl_command(self) -> tuple[str, ...]:
        return (self.frida_path or "frida", "-H", self.ENDPOINT)

    def build_trace_command(
        self, target: FridaTarget | None, pattern: str | None = None
    ) -> tuple[str, ...]:
        value = self._target_name(target)
        command = [self.frida_trace_path or "frida-trace", "-H", self.ENDPOINT, "-n", value]
        if pattern and pattern.strip():
            command.extend(("-i", pattern.strip()))
        return tuple(command)

    def readiness(
        self, serial: str | None, target: FridaTarget | None = None,
        *, require_pid: bool = False, require_application: bool = False,
        trace: bool = False, require_target: bool = True,
    ) -> FridaSessionReadiness:
        errors: list[str] = []
        executable = self.frida_trace_path if trace else self.frida_path
        if not executable:
            errors.append(f"{'frida-trace' if trace else 'Frida'} was not found in PATH.")
        if not serial:
            errors.append("No device is selected.")
        if target is None and require_target:
            errors.append("No target is selected.")
        elif target is not None and require_pid and target.pid is None:
            errors.append("The selected target has no PID.")
        elif target is not None and require_application and not target.application_identifier:
            errors.append("The selected target has no application identifier.")
        if not serial:
            return FridaSessionReadiness(False, errors=tuple(errors))

        diagnosis = self.frida.diagnose(serial)
        if not diagnosis.server_running:
            errors.append("frida-server is not running on the selected device.")
        if not diagnosis.port_27042:
            errors.append("TCP 27042 forwarding is unavailable.")
        warning = self.version_mismatch_warning(
            diagnosis.host_version, diagnosis.server_version
        ) if diagnosis.versions_match is False else None
        return FridaSessionReadiness(
            not errors, warning, tuple(errors), diagnosis.host_version, diagnosis.server_version
        )

    def launch(self, command: Sequence[str]) -> CommandResult:
        executable = command[0] if command else ""
        if not executable or executable in {"frida", "frida-trace"}:
            return CommandResult.from_command(command, -1, error=f"{executable or 'Frida'} was not found in PATH.")
        return self.terminal.launch(command)

    def launch_attach(self, target: FridaTarget | None) -> CommandResult:
        return self.launch(self.build_attach_command(target))

    def launch_pid(self, target: FridaTarget | None) -> CommandResult:
        return self.launch(self.build_pid_command(target))

    def launch_spawn(self, target: FridaTarget | None) -> CommandResult:
        return self.launch(self.build_spawn_command(target))

    def launch_repl(self) -> CommandResult:
        return self.launch(self.build_repl_command())

    def launch_trace(
        self, target: FridaTarget | None, pattern: str | None = None
    ) -> CommandResult:
        return self.launch(self.build_trace_command(target, pattern))

    def build_command_preview(
        self, command: Sequence[str], platform_name: str | None = None
    ) -> str:
        return self.preview(command, platform_name)

    @staticmethod
    def preview(command: Sequence[str], platform_name: str | None = None) -> str:
        args = tuple(str(part) for part in command)
        return subprocess.list2cmdline(args) if (platform_name or os.name) == "nt" else shlex.join(args)

    @staticmethod
    def version_mismatch_warning(host: str | None, server: str | None) -> str:
        host_text = host or "unknown"
        server_text = server or "unknown"
        side = "Neither side could be compared"
        host_parts = FridaSessionManager._version_parts(host)
        server_parts = FridaSessionManager._version_parts(server)
        if host_parts and server_parts:
            if host_parts > server_parts:
                side = "Host Frida is newer"
            elif server_parts > host_parts:
                side = "Device frida-server is newer"
            else:
                side = "Numeric versions match, but the builds differ"
        return (
            f"Frida version mismatch: host {host_text}; server {server_text}. {side}. "
            "Attachment may be unreliable. Install matching versions manually before critical work."
        )

    @staticmethod
    def _target_name(target: FridaTarget | None) -> str:
        if target is None:
            raise ValueError("No target is selected.")
        value = target.identifier or target.name
        if not value:
            raise ValueError("The selected target has no attachable name.")
        return value

    @staticmethod
    def _version_parts(value: str | None) -> tuple[int, ...]:
        if not value:
            return ()
        match = re.search(r"\d+(?:\.\d+)+", value)
        return tuple(int(part) for part in match.group(0).split(".")) if match else ()
