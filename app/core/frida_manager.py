"""Selected-device Frida diagnostics and lifecycle management."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

from app.core.adb_manager import ADBManager
from app.core.command_result import CommandResult
from app.core.command_runner import CommandRunner
from app.core.host_tool_resolver import HostToolResolver


@dataclass(frozen=True, slots=True)
class ForwardingStatus:
    port_27042: bool = False
    port_27043: bool = False
    result: CommandResult | None = None


@dataclass(frozen=True, slots=True)
class ManagedForwardingRepair:
    serial: str | None
    managed_ports: tuple[str, ...] = ()
    repaired_ports: tuple[str, ...] = ()
    preserved_ports: tuple[str, ...] = ()
    results: tuple[CommandResult, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors and all(result.ok for result in self.results)


@dataclass(frozen=True, slots=True)
class FridaDiagnosis:
    serial: str | None
    adb_available: bool
    root_available: bool
    server_running: bool
    server_path: str | None
    host_version: str | None
    server_version: str | None
    versions_match: bool | None
    port_27042: bool
    port_27043: bool
    reachable: bool
    recommendations: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)


class FridaManager:
    SERVER_PATHS = (
        "/data/local/tmp/frida-server",
        "/data/adb/frida/frida-server",
    )

    def __init__(
        self,
        adb: ADBManager,
        runner: CommandRunner,
        *,
        frida_path: str | None = None,
        frida_ps_path: str | None = None,
        resolver: HostToolResolver | None = None,
    ):
        self.adb = adb
        self.runner = runner
        self._frida_explicit = frida_path is not None
        self._frida_ps_explicit = frida_ps_path is not None
        self.resolver = resolver or HostToolResolver()
        self.frida_path = self.resolver.resolve("frida") if frida_path is None else frida_path
        self.frida_ps_path = self.resolver.resolve("frida-ps") if frida_ps_path is None else frida_ps_path
        self._managed_forwarding: set[tuple[str, str]] = set()

    @staticmethod
    def _serial_error(operation: str) -> CommandResult:
        return CommandResult.from_command(
            (operation,), -1, error="No device is selected."
        )

    def host_version(self) -> CommandResult:
        executable = self.frida_path if self._frida_explicit else self.resolver.resolve("frida")
        if not executable:
            return CommandResult.from_command(
                ("frida", "--version"), -1,
                error=self.resolver.missing_message("frida", "Frida"),
            )
        self.frida_path = executable
        return self.runner.run((executable, "--version"), timeout=10)

    def server_version(self, serial: str | None) -> CommandResult:
        if not serial:
            return self._serial_error("frida-server --version")
        path = self.locate_server(serial)
        if not path:
            return CommandResult.from_command(
                ("adb", "-s", serial, "shell", "su", "-c", "frida-server --version"),
                -1,
                error="frida-server was not found on the selected device.",
            )
        return self.adb.run(
            "shell", "su", "-c", f"{shlex.quote(path)} --version",
            serial=serial, timeout=10,
        )

    def server_running(self, serial: str | None) -> bool:
        if not serial:
            return False
        result = self.adb.run(
            "shell", "su", "-c", "pidof frida-server", serial=serial, timeout=8
        )
        return result.ok and bool(result.stdout.strip())

    def locate_server(self, serial: str | None) -> str | None:
        if not serial:
            return None
        command = (
            "for f in /data/local/tmp/frida-server "
            "/data/local/tmp/frida-server-* /data/adb/frida/frida-server; "
            "do [ -f \"$f\" ] && printf '%s\\n' \"$f\"; done"
        )
        result = self.adb.run("shell", "su", "-c", command, serial=serial, timeout=10)
        if not result.ok:
            return None
        for line in result.stdout.splitlines():
            path = line.strip()
            if path in self.SERVER_PATHS or path.startswith("/data/local/tmp/frida-server-"):
                return path
        return None

    def root_available(self, serial: str | None) -> bool:
        if not serial:
            return False
        result = self.adb.run("shell", "su", "-c", "id", serial=serial, timeout=8)
        return result.ok and "uid=0" in result.stdout

    def forwarding_status(self, serial: str | None) -> ForwardingStatus:
        if not serial:
            return ForwardingStatus(result=self._serial_error("adb forward --list"))
        result = self.adb.run("forward", "--list", serial=serial, timeout=10)
        if not result.ok:
            return ForwardingStatus(result=result)
        ports: set[str] = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == serial and parts[1] == parts[2]:
                ports.add(parts[1])
        return ForwardingStatus("tcp:27042" in ports, "tcp:27043" in ports, result)

    def repair_forwarding(self, serial: str | None) -> tuple[CommandResult, CommandResult]:
        if not serial:
            error = self._serial_error("adb forward")
            return error, error
        results = (
            self.adb.run("forward", "tcp:27042", "tcp:27042", serial=serial, timeout=10),
            self.adb.run("forward", "tcp:27043", "tcp:27043", serial=serial, timeout=10),
        )
        for port, result in zip(("tcp:27042", "tcp:27043"), results):
            if result.ok:
                self._managed_forwarding.add((serial, port))
        return results

    def managed_forwarding_ports(self, serial: str | None) -> tuple[str, ...]:
        if not serial:
            return ()
        return tuple(
            sorted(port for owner, port in self._managed_forwarding if owner == serial)
        )

    def repair_managed_forwarding(self, serial: str | None) -> ManagedForwardingRepair:
        if not serial:
            return ManagedForwardingRepair(
                None, errors=("No device is selected.",)
            )
        managed = self.managed_forwarding_ports(serial)
        if not managed:
            return ManagedForwardingRepair(
                serial,
                errors=(
                    "No SUS Companion-managed Frida forwarding exists for this serial.",
                ),
            )
        status = self.forwarding_status(serial)
        if not status.result or not status.result.ok:
            return ManagedForwardingRepair(
                serial,
                managed_ports=managed,
                errors=(
                    status.result.output
                    if status.result and status.result.output
                    else "Unable to inspect ADB forwarding.",
                ),
            )
        present = {
            "tcp:27042" if status.port_27042 else "",
            "tcp:27043" if status.port_27043 else "",
        }
        repaired = []
        preserved = []
        results = []
        errors = []
        for port in managed:
            if port in present:
                preserved.append(port)
                continue
            result = self.adb.run("forward", port, port, serial=serial, timeout=10)
            results.append(result)
            if result.ok:
                repaired.append(port)
            else:
                errors.append(result.output or f"Unable to repair {port}.")
        return ManagedForwardingRepair(
            serial,
            managed,
            tuple(repaired),
            tuple(preserved),
            tuple(results),
            tuple(errors),
        )

    def list_processes(self, serial: str | None) -> CommandResult:
        return self._list(serial, applications=False)

    def list_applications(self, serial: str | None) -> CommandResult:
        return self._list(serial, applications=True)

    def _list(self, serial: str | None, *, applications: bool) -> CommandResult:
        if not serial:
            return self._serial_error("frida-ps")
        executable = self.frida_ps_path if self._frida_ps_explicit else self.resolver.resolve("frida-ps")
        if not executable:
            return CommandResult.from_command(
                ("frida-ps",), -1,
                error=self.resolver.missing_message("frida-ps"),
            )
        self.frida_ps_path = executable
        args = [executable, "-H", "127.0.0.1:27042"]
        if applications:
            args.append("-ai")
        return self.runner.run(args, timeout=30)

    def start_server(self, serial: str | None, path: str | None = None) -> CommandResult:
        if not serial:
            return self._serial_error("start frida-server")
        selected_path = path or self.locate_server(serial)
        if not selected_path:
            return CommandResult.from_command(
                ("adb", "-s", serial, "shell", "su", "-c"), -1,
                error="frida-server was not found on the selected device.",
            )
        if self._expected_server_ready(serial, selected_path):
            return CommandResult.from_command(
                ("adb", "-s", serial, "shell", "su", "-c", selected_path), 0,
                stdout="Frida server is already running.",
            )
        quoted = shlex.quote(selected_path)
        command = f"chmod 755 {quoted} && {quoted} >/dev/null 2>&1 &"
        result = self.adb.run("shell", "su", "-c", command, serial=serial, timeout=12)
        address_in_use = "address already in use" in result.output.casefold()
        if address_in_use and self._expected_server_ready(serial, selected_path):
            return CommandResult.from_command(result.command, 0, stdout="Frida server is already running.")
        return result

    def _expected_server_ready(self, serial: str, expected_path: str) -> bool:
        if not self.server_running(serial):
            return False
        located = self.locate_server(serial)
        if located != expected_path:
            return False
        return self.forwarding_status(serial).port_27042

    def stop_server(self, serial: str | None) -> CommandResult:
        if not serial:
            return self._serial_error("stop frida-server")
        return self.adb.run(
            "shell", "su", "-c", "pkill -f frida-server", serial=serial, timeout=10
        )

    def restart_server(self, serial: str | None, path: str | None = None) -> tuple[CommandResult, CommandResult]:
        stop = self.stop_server(serial)
        if not serial:
            return stop, self._serial_error("start frida-server")
        return stop, self.start_server(serial, path)

    def diagnose(self, serial: str | None) -> FridaDiagnosis:
        errors: list[str] = []
        recommendations: list[str] = []
        adb_available = self.adb.exists()
        if not serial:
            return FridaDiagnosis(
                serial=None, adb_available=adb_available, root_available=False,
                server_running=False, server_path=None, host_version=None,
                server_version=None, versions_match=None, port_27042=False,
                port_27043=False, reachable=False,
                recommendations=("Select an online Android device.",),
                errors=("No device is selected.",),
            )

        root = self.root_available(serial) if adb_available else False
        running = self.server_running(serial) if adb_available else False
        path = self.locate_server(serial) if adb_available else None
        host_result = self.host_version()
        server_result = self.server_version(serial) if path else None
        host_version = self._extract_version(host_result.stdout) if host_result.ok else None
        server_version = self._extract_version(server_result.stdout) if server_result and server_result.ok else None
        match = host_version == server_version if host_version and server_version else None
        forwarding = self.forwarding_status(serial) if adb_available else ForwardingStatus()
        reach_result = self.list_processes(serial) if running and forwarding.port_27042 else None
        reachable = bool(reach_result and reach_result.ok)

        if not adb_available:
            recommendations.append("Install ADB and ensure it is available in PATH.")
        if not root:
            recommendations.append("Confirm the selected device grants root access through su.")
        if not path:
            recommendations.append("Place a compatible frida-server on the device; it will not be installed automatically.")
        elif not running:
            recommendations.append("Start frida-server explicitly from the control center.")
        if not host_result.ok:
            recommendations.append("Install the Frida host tools, including frida and frida-ps.")
            errors.append(host_result.output)
        if match is False:
            recommendations.append("Use matching host Frida and device frida-server versions.")
        if not forwarding.port_27042 or not forwarding.port_27043:
            recommendations.append("Repair TCP forwarding for ports 27042 and 27043.")
        if running and forwarding.port_27042 and not reachable:
            recommendations.append("Check frida-server output, architecture, and host connectivity.")
            if reach_result and reach_result.output:
                errors.append(reach_result.output)
        if not recommendations:
            recommendations.append("Frida is ready for the selected device.")

        return FridaDiagnosis(
            serial, adb_available, root, running, path, host_version, server_version,
            match, forwarding.port_27042, forwarding.port_27043, reachable,
            tuple(recommendations), tuple(error for error in errors if error),
        )

    @staticmethod
    def _extract_version(output: str) -> str | None:
        match = re.search(r"\d+(?:\.\d+)+(?:[-+._a-zA-Z0-9]*)?", output)
        return match.group(0) if match else None
