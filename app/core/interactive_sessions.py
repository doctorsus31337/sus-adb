"""Host-side lifecycle control for interactive sessions launched in real terminals."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Sequence

from app.core.command_router import CommandRoute
from app.core.external_terminal import ExternalTerminal
from app.core.frida_target import FridaTarget, TargetType
from app.core.instrumentation_launch import (
    InstrumentationLaunchDescriptor,
    classify_target,
    normalize_transport,
)


INSTRUMENTATION_SESSION_TYPES = frozenset(("objection", "frida-repl", "frida-trace"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InteractiveSessionType(str, Enum):
    ADB_SHELL = "adb-shell"
    ROOT_SHELL = "root-shell"
    ADB_LOGCAT = "adb-logcat"
    OBJECTION = "objection"
    FRIDA_REPL = "frida-repl"
    FRIDA_TRACE = "frida-trace"
    HOST_SHELL = "host-shell"


class InteractiveSessionState(str, Enum):
    PREPARING = "preparing"
    LAUNCHING = "launching"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXITED = "exited"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SessionLaunchPlan:
    session_type: InteractiveSessionType
    command: tuple[str, ...]
    serial: str = ""
    target: str = ""
    endpoint: str = ""
    attach_mode: str = ""
    script_path: str = ""
    executable: str = ""
    prerequisites: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    explanation: str = ""
    descriptor: InstrumentationLaunchDescriptor | None = None

    @property
    def ready(self) -> bool:
        return bool(self.command and not self.errors)

    def preview(self, platform_name: str | None = None) -> str:
        return (
            subprocess.list2cmdline(self.command)
            if (platform_name or os.name) in {"nt", "windows", "win32"}
            else __import__("shlex").join(self.command)
        )


@dataclass(frozen=True, slots=True)
class InteractiveSessionRecord:
    session_id: str
    session_type: InteractiveSessionType
    serial: str
    target: str
    endpoint: str
    command: tuple[str, ...]
    start_time: str
    state: InteractiveSessionState
    backend: str = ""
    external: bool = True
    prompt_ready_time: str = ""
    last_error: str = ""
    diagnostics: tuple[str, ...] = ()
    stages: tuple[tuple[str, str], ...] = ()
    technical_details: str = ""
    command_history: tuple[str, ...] = ()
    descriptor: InstrumentationLaunchDescriptor | None = None


@dataclass(frozen=True, slots=True)
class SessionOperationResult:
    ok: bool
    record: InteractiveSessionRecord | None = None
    error: str = ""


class InteractiveSessionManager:
    ACTIVE = frozenset(
        (
            InteractiveSessionState.PREPARING,
            InteractiveSessionState.LAUNCHING,
            InteractiveSessionState.CONNECTED,
        )
    )

    def __init__(
        self,
        terminal: ExternalTerminal,
        resolver,
        *,
        selected_serial_provider: Callable[[], str | None] = lambda: None,
        adb_path_provider: Callable[[], str | None] = lambda: None,
        objection_manager=None,
        frida_sessions=None,
        objection_recovery=None,
        clock: Callable[[], str] = utc_now,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        singleton_types: Sequence[str] = (),
    ):
        self.terminal = terminal
        self.resolver = resolver
        self.selected_serial_provider = selected_serial_provider
        self.adb_path_provider = adb_path_provider
        self.objection_manager = objection_manager
        self.frida_sessions = frida_sessions
        self.objection_recovery = objection_recovery
        self.clock = clock
        self.id_factory = id_factory
        self.singleton_types = frozenset(InteractiveSessionType(value) for value in singleton_types)
        self.records: dict[str, InteractiveSessionRecord] = {}
        self._plans: dict[str, SessionLaunchPlan] = {}
        self._processes: dict[str, object] = {}
        self._listeners = []
        self._lock = threading.RLock()

    def subscribe(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)
        return lambda: self._listeners.remove(callback) if callback in self._listeners else None

    def _changed(self, record):
        for callback in tuple(self._listeners):
            callback(record)

    def _put(self, record):
        with self._lock:
            self.records[record.session_id] = record
        self._changed(record)
        return record

    def list(self):
        with self._lock:
            return tuple(sorted(self.records.values(), key=lambda value: (value.start_time, value.session_id)))

    def _resolve(self, name: str, preferred: str | None = None) -> str:
        if preferred:
            path = Path(preferred).expanduser()
            if path.is_absolute():
                return str(path)
        return self.resolver.resolve(name) or ""

    def build_adb_shell(
        self,
        serial: str,
        *,
        root: bool = False,
        root_available: bool = False,
        root_confirmed: bool = False,
    ) -> SessionLaunchPlan:
        errors = []
        executable = self._resolve("adb", self.adb_path_provider())
        if not executable:
            errors.append(self.resolver.missing_message("adb", "ADB"))
        if not serial:
            errors.append("Select a device explicitly.")
        if root and not root_available:
            errors.append("Existing root was not detected; SUS Companion will not acquire root.")
        if root and not root_confirmed:
            errors.append("Root shell requires explicit confirmation.")
        command = (executable or "adb", "-s", serial, "shell") + (("su",) if root else ())
        return SessionLaunchPlan(
            InteractiveSessionType.ROOT_SHELL if root else InteractiveSessionType.ADB_SHELL,
            command,
            serial,
            executable=executable,
            prerequisites=("ADB authorization", "Explicit selected serial") + (("Existing root",) if root else ()),
            errors=tuple(errors),
            explanation="A dedicated external terminal owns the interactive Android shell.",
        )

    def build_objection(
        self,
        serial: str,
        target: str,
        *,
        spawn: bool = False,
        transport: str = "network",
        host: str = "127.0.0.1",
        port: int | str = 27042,
    ) -> SessionLaunchPlan:
        errors = []
        executable = self._resolve(
            "objection", getattr(self.objection_manager, "objection_path", None)
        )
        if not serial:
            errors.append("Select a device explicitly.")
        target_value = target.strip()
        if not target_value:
            errors.append("Select an application or process target.")
        if not executable:
            errors.append(self.resolver.missing_message("objection", "Objection"))
        normalized_transport = normalize_transport(transport)
        try:
            network_port = int(port) if normalized_transport == "network" else 0
        except (TypeError, ValueError):
            network_port = 0
        target_kind = classify_target(target_value)
        descriptor = InstrumentationLaunchDescriptor(
            backend="objection",
            operation="start",
            mode="spawn" if spawn else "attach",
            target_kind=target_kind,
            target=target_value,
            transport=normalized_transport,
            device_serial=serial,
            usb_serial=serial if normalized_transport == "usb" else "",
            network_host=host.strip() if normalized_transport == "network" else "",
            network_port=network_port,
        )
        try:
            self._validate_descriptor(descriptor)
        except ValueError as exc:
            errors.append(str(exc))
        try:
            builder = (
                self.objection_manager.build_spawn_command
                if spawn else self.objection_manager.build_attach_command
            )
            command = builder(
                target_value, normalized_transport, serial,
                host=descriptor.network_host, port=descriptor.network_port or port,
            )
            command = (executable or command[0], *command[1:])
        except (AttributeError, ValueError) as exc:
            command = (executable or "objection",)
            errors.append(str(exc))
        return SessionLaunchPlan(
            InteractiveSessionType.OBJECTION,
            tuple(command),
            serial,
            target_value,
            descriptor.endpoint,
            "spawn" if spawn else "attach",
            executable=executable,
            prerequisites=("Frida route reachable", "Explicit selected target"),
            errors=tuple(dict.fromkeys(errors)),
            explanation="Objection connects in a dedicated terminal and may take time to load its agent.",
            descriptor=descriptor,
        )

    def build_frida(
        self,
        serial: str,
        target: FridaTarget | None,
        *,
        mode: str = "attach",
        endpoint: str = "127.0.0.1:27042",
        script_path: str = "",
        trace: bool = False,
        trace_pattern: str = "",
        trace_options: Sequence[tuple[str, str]] = (),
    ) -> SessionLaunchPlan:
        tool = "frida-trace" if trace else "frida"
        preferred = (
            getattr(self.frida_sessions, "frida_trace_path", None)
            if trace else getattr(self.frida_sessions, "frida_path", None)
        )
        executable = self._resolve(tool, preferred)
        errors = []
        if not executable:
            errors.append(self.resolver.missing_message(tool, "Frida" if not trace else None))
        if not serial:
            errors.append("Select a device explicitly.")
        if target is None:
            errors.append("Select a Frida target.")
        try:
            network_host, network_port = self._split_endpoint(endpoint)
        except ValueError as exc:
            network_host, network_port = "", 0
            errors.append(str(exc))
        command: list[str] = []
        target_name = ""
        target_kind = ""
        if target is not None:
            if mode == "spawn":
                target_name = target.application_identifier or ""
                target_kind = "application"
                if not target_name:
                    errors.append("Spawn requires an application package identifier.")
            elif mode == "pid":
                target_name = str(target.pid or "")
                target_kind = "pid"
                if not target.pid:
                    errors.append("PID attach requires a running process ID.")
            elif mode == "frontmost":
                target_kind = "frontmost"
                target_name = "frontmost"
            else:
                target_name = target.application_identifier or target.name or target.identifier
                target_kind = "application" if target.application_identifier else "name"
                if not target_name:
                    errors.append("Attach requires a target name or package.")
        resolved_script = ""
        if script_path:
            path = Path(script_path).expanduser().resolve()
            if not path.is_file():
                errors.append("Select an existing local Frida script.")
            else:
                resolved_script = str(path)
        canonical_trace_options = tuple(
            (str(flag), str(value)) for flag, value in trace_options
        ) or ((("-i", trace_pattern.strip()),) if trace and trace_pattern.strip() else ())
        descriptor = InstrumentationLaunchDescriptor(
            backend="frida-trace" if trace else "frida",
            operation="trace" if trace else "repl",
            mode=mode,
            target_kind=target_kind,
            target=target_name,
            transport="network",
            device_serial=serial,
            network_host=network_host,
            network_port=network_port,
            trace_options=canonical_trace_options,
            script_path=resolved_script,
        )
        try:
            self._validate_descriptor(descriptor)
        except ValueError as exc:
            errors.append(str(exc))
        try:
            command = list(self._frida_command(descriptor, target, executable or tool))
        except (AttributeError, ValueError) as exc:
            command = [executable or tool]
            errors.append(str(exc))
        return SessionLaunchPlan(
            InteractiveSessionType.FRIDA_TRACE if trace else InteractiveSessionType.FRIDA_REPL,
            tuple(command),
            serial,
            target_name,
            endpoint,
            mode,
            resolved_script,
            executable,
            ("Frida endpoint reachable", "Explicit selected target"),
            tuple(dict.fromkeys(errors)),
            "Frida runs in a dedicated terminal; prompt readiness depends on target and agent loading.",
            descriptor,
        )

    def _frida_command(
        self,
        descriptor: InstrumentationLaunchDescriptor,
        target: FridaTarget | None,
        executable: str,
    ) -> tuple[str, ...]:
        endpoint = descriptor.endpoint
        if descriptor.backend == "frida-trace":
            command = self.frida_sessions.build_trace_command(
                target, None, mode=descriptor.mode, endpoint=endpoint
            )
            command = (*command, *(part for option in descriptor.trace_options for part in option))
        elif descriptor.mode == "spawn":
            command = self.frida_sessions.build_spawn_command(target, endpoint=endpoint)
        elif descriptor.mode == "pid":
            command = self.frida_sessions.build_pid_command(target, endpoint=endpoint)
        elif descriptor.mode == "frontmost":
            command = (self.frida_sessions.frida_path or "frida", "-H", endpoint, "-F")
        else:
            command = self.frida_sessions.build_attach_command(target, endpoint=endpoint)
        command = (executable, *command[1:])
        if descriptor.script_path:
            command = (*command, "-l", descriptor.script_path)
        return tuple(command)

    @staticmethod
    def _split_endpoint(endpoint: str) -> tuple[str, int]:
        value = endpoint.strip()
        if not value or ":" not in value:
            raise ValueError("Network endpoint must be host:port.")
        host, port_text = value.rsplit(":", 1)
        if not host or any(character in host for character in "\x00\r\n"):
            raise ValueError("Network host is required and must not contain control characters.")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("Network port must be a number from 1 to 65535.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Network port must be from 1 to 65535.")
        return host, port

    @staticmethod
    def _target_from_descriptor(
        descriptor: InstrumentationLaunchDescriptor,
    ) -> FridaTarget | None:
        if descriptor.target_kind == "frontmost":
            return FridaTarget("Frontmost application", None, None, TargetType.APPLICATION, True)
        if descriptor.target_kind == "pid":
            return FridaTarget(
                descriptor.target, None, int(descriptor.target), TargetType.PROCESS, True
            )
        if descriptor.target_kind == "application":
            return FridaTarget(
                descriptor.target, descriptor.target, None, TargetType.APPLICATION,
                descriptor.mode != "spawn",
            )
        if descriptor.target_kind == "name":
            return FridaTarget(
                descriptor.target, None, None, TargetType.PROCESS, True
            )
        return None

    def plan_from_route(
        self, route: CommandRoute, selected_serial: str, target: FridaTarget | None = None
    ) -> SessionLaunchPlan:
        route_serial = route.serial or selected_serial
        errors = []
        if route.serial and selected_serial and route.serial != selected_serial:
            errors.append("Command serial does not match the explicitly selected device.")
        if route.session_type == "adb-shell":
            plan = self.build_adb_shell(route_serial)
            return replace(plan, errors=tuple((*plan.errors, *errors)))
        if route.session_type == "adb-logcat":
            executable = self._resolve("adb", self.adb_path_provider())
            command = list(route.resolved_argv or route.argv)
            if "-s" not in command and route_serial:
                command[1:1] = ("-s", route_serial)
            return SessionLaunchPlan(
                InteractiveSessionType.ADB_LOGCAT, tuple(command), route_serial,
                executable=executable, errors=tuple(errors),
                explanation="Live Logcat runs in a dedicated terminal until interrupted.",
            )
        if route.session_type == "objection":
            command = list(route.resolved_argv or route.argv)
            executable = self._resolve("objection", command[0] if command else None)
            if executable and command:
                command[0] = executable
            if not executable:
                errors.append(self.resolver.missing_message("objection", "Objection"))
            if not route_serial:
                errors.append("Select a device explicitly.")
            descriptor = None
            try:
                descriptor = self._descriptor_from_command(
                    InteractiveSessionType.OBJECTION, route_serial, command
                )
            except ValueError as exc:
                errors.append(f"Objection route is incomplete: {exc}")
            return SessionLaunchPlan(
                InteractiveSessionType.OBJECTION, tuple(command), route_serial,
                descriptor.target if descriptor else (
                    route.target or (target.identifier if target and target.identifier else "")
                ),
                descriptor.endpoint if descriptor else "",
                "spawn" if "-s" in command else "attach",
                executable=executable, errors=tuple(errors), explanation=route.reason,
                descriptor=descriptor,
            )
        if route.session_type in {"frida-repl", "frida-trace"}:
            command = list(route.resolved_argv or route.argv)
            tool = "frida" if route.session_type == "frida-repl" else "frida-trace"
            executable = self._resolve(tool, command[0] if command else None)
            if executable and command:
                command[0] = executable
            if not executable:
                errors.append("The interactive executable could not be resolved to an absolute path.")
            if not route_serial:
                errors.append("Select a device explicitly.")
            descriptor = None
            try:
                descriptor = self._descriptor_from_command(
                    InteractiveSessionType(route.session_type), route_serial, command
                )
            except ValueError as exc:
                errors.append(f"Frida route is incomplete: {exc}")
            return SessionLaunchPlan(
                InteractiveSessionType(route.session_type), tuple(command), route_serial,
                descriptor.target if descriptor else route.target,
                descriptor.endpoint if descriptor else "",
                descriptor.mode if descriptor else "", executable=executable,
                errors=tuple(errors), explanation=route.reason,
                descriptor=descriptor,
            )
        if route.session_type == "host-shell":
            command=route.resolved_argv or route.argv
            executable=self._resolve(Path(command[0]).name,command[0]) if command else ""
            return SessionLaunchPlan(
                InteractiveSessionType.HOST_SHELL, (executable,*command[1:]) if executable else command,
                executable=executable, errors=() if executable else ("Host shell executable could not be resolved.",), explanation=route.reason,
            )
        return SessionLaunchPlan(
            InteractiveSessionType.HOST_SHELL, (), errors=("Unsupported interactive route.",)
        )

    def launch(self, plan: SessionLaunchPlan) -> SessionOperationResult:
        if not plan.ready:
            return SessionOperationResult(False, error="; ".join(plan.errors) or "Session plan is not ready.")
        if plan.session_type.value in INSTRUMENTATION_SESSION_TYPES:
            if plan.descriptor is None:
                return SessionOperationResult(
                    False,
                    error="Instrumentation launch requires a complete canonical descriptor.",
                )
            try:
                self._validate_descriptor(plan.descriptor)
            except ValueError as exc:
                return SessionOperationResult(False, error=str(exc))
        if plan.serial and self.selected_serial_provider() != plan.serial:
            return SessionOperationResult(False, error="Selected device changed; session was not launched.")
        if plan.session_type in self.singleton_types:
            existing = next(
                (
                    record for record in self.list()
                    if record.session_type is plan.session_type
                    and record.serial == plan.serial
                    and record.target == plan.target
                    and record.state in self.ACTIVE
                ),
                None,
            )
            if existing:
                return SessionOperationResult(True, existing)
        session_id = self.id_factory()
        record = InteractiveSessionRecord(
            session_id, plan.session_type, plan.serial, plan.target, plan.endpoint,
            plan.command, self.clock(), InteractiveSessionState.PREPARING,
            diagnostics=(plan.explanation, *plan.prerequisites),
            stages=(("process launch", self.clock()),),
            descriptor=plan.descriptor,
        )
        self._put(record)
        record = self._put(
            replace(
                record,
                state=InteractiveSessionState.LAUNCHING,
                stages=(*record.stages, ("external terminal", self.clock())),
            )
        )
        launched = self.terminal.launch_tracked(
            plan.command, title=f"SUS Companion — {plan.session_type.value}"
        )
        if not launched.result.ok:
            record = self._put(
                replace(
                    record, state=InteractiveSessionState.FAILED,
                    backend=launched.backend, last_error=launched.result.error or launched.result.output,
                )
            )
            return SessionOperationResult(False, record, record.last_error)
        self._plans[session_id] = plan
        if launched.process is not None:
            self._processes[session_id] = launched.process
        record = self._put(
            replace(
                record, state=InteractiveSessionState.CONNECTED,
                backend=launched.backend,
                stages=(
                    *record.stages,
                    ("terminal launched", self.clock()),
                    *(
                        (
                            ("Frida connection", "Observe in external terminal"),
                            ("agent load", "Observe in external terminal"),
                            ("prompt ready", "Not observable by external backend"),
                        )
                        if plan.session_type is InteractiveSessionType.OBJECTION
                        else ()
                    ),
                ),
            )
        )
        return SessionOperationResult(True, record)

    def reconnect(self, session_id: str) -> SessionOperationResult:
        record = self.records.get(session_id)
        if not record:
            return SessionOperationResult(False, error="Session record cannot be reconnected.")
        if record.serial and self.selected_serial_provider() != record.serial:
            return SessionOperationResult(False, record, "Reconnect requires the same explicitly selected serial.")
        if record.session_type.value in INSTRUMENTATION_SESSION_TYPES:
            descriptor = record.descriptor
            if descriptor is None:
                try:
                    descriptor = self._descriptor_from_command(
                        record.session_type, record.serial, record.command
                    )
                except ValueError as exc:
                    return SessionOperationResult(
                        False, record,
                        f"Legacy session cannot be reconnected safely: {exc}",
                    )
            expected_backend = {
                InteractiveSessionType.OBJECTION: "objection",
                InteractiveSessionType.FRIDA_REPL: "frida",
                InteractiveSessionType.FRIDA_TRACE: "frida-trace",
            }[record.session_type]
            if descriptor.backend != expected_backend:
                return SessionOperationResult(
                    False, record,
                    "Reconnect descriptor backend does not match the stored session type.",
                )
            try:
                plan = self._rebuild_instrumentation_plan(descriptor)
            except ValueError as exc:
                return SessionOperationResult(False, record, str(exc))
            readiness_errors = self._reconnect_readiness_errors(descriptor)
            if readiness_errors:
                return SessionOperationResult(
                    False, record,
                    "Reconnect readiness failed: " + "; ".join(readiness_errors),
                )
        else:
            plan = self._plans.get(session_id)
            if plan is None:
                return SessionOperationResult(
                    False, record,
                    "Legacy session has no complete launch descriptor; reconnect would require guessing.",
                )
        return self.launch(plan)

    def _rebuild_instrumentation_plan(
        self, descriptor: InstrumentationLaunchDescriptor
    ) -> SessionLaunchPlan:
        self._validate_descriptor(descriptor)
        if descriptor.backend == "objection":
            return self.build_objection(
                descriptor.device_serial,
                descriptor.target,
                spawn=descriptor.mode == "spawn",
                transport=descriptor.transport,
                host=descriptor.network_host,
                port=descriptor.network_port,
            )
        target = self._target_from_descriptor(descriptor)
        return self.build_frida(
            descriptor.device_serial,
            target,
            mode=descriptor.mode,
            endpoint=descriptor.endpoint,
            script_path=descriptor.script_path,
            trace=descriptor.backend == "frida-trace",
            trace_options=descriptor.trace_options,
        )

    def _reconnect_readiness_errors(
        self, descriptor: InstrumentationLaunchDescriptor
    ) -> tuple[str, ...]:
        if descriptor.backend == "objection":
            readiness = self.objection_manager.readiness(
                descriptor.device_serial,
                descriptor.target,
                descriptor.transport,
                spawn=descriptor.mode == "spawn",
                host=descriptor.network_host,
                port=descriptor.network_port,
            )
        else:
            target = self._target_from_descriptor(descriptor)
            readiness = self.frida_sessions.readiness(
                descriptor.device_serial,
                target,
                require_pid=descriptor.mode == "pid",
                require_application=descriptor.mode == "spawn",
                trace=descriptor.backend == "frida-trace",
            )
        return tuple(readiness.errors)

    @staticmethod
    def _validate_descriptor(descriptor: InstrumentationLaunchDescriptor) -> None:
        expected_operation = {
            "objection": "start", "frida": "repl", "frida-trace": "trace",
        }
        if descriptor.backend not in expected_operation:
            raise ValueError("Launch descriptor has an unsupported instrumentation backend.")
        if descriptor.operation != expected_operation[descriptor.backend]:
            raise ValueError("Launch descriptor operation does not match its backend.")
        if descriptor.mode not in {"attach", "spawn", "pid", "frontmost"}:
            raise ValueError("Launch descriptor has an unsupported launch mode.")
        if descriptor.mode == "spawn" and descriptor.target_kind != "application":
            raise ValueError("Spawn requires a package/application identifier.")
        if descriptor.mode == "pid" and descriptor.target_kind != "pid":
            raise ValueError("PID attach requires a stored numeric PID target.")
        if descriptor.mode == "frontmost" and descriptor.target_kind != "frontmost":
            raise ValueError("Frontmost attach requires the frontmost target selector.")
        if descriptor.mode == "attach" and descriptor.target_kind not in {"application", "name"}:
            raise ValueError("Attach requires a stored application identifier or process name.")
        if descriptor.backend == "objection" and descriptor.target_kind == "pid":
            raise ValueError("Objection cannot use a PID target.")
        if descriptor.backend == "objection" and descriptor.mode not in {"attach", "spawn"}:
            raise ValueError("Objection supports attach or spawn mode only.")
        if descriptor.mode != "frontmost" and not descriptor.target:
            raise ValueError("Launch descriptor is missing its exact target.")
        if descriptor.transport == "usb":
            if not descriptor.usb_serial:
                raise ValueError("Launch descriptor is missing the exact USB serial.")
            if descriptor.device_serial and descriptor.usb_serial != descriptor.device_serial:
                raise ValueError("USB serial does not match the explicitly selected device.")
        elif descriptor.transport == "network":
            if not descriptor.network_host or not 1 <= descriptor.network_port <= 65535:
                raise ValueError("Launch descriptor is missing a valid network host/port.")
            if any(character.isspace() or character == "\x00" for character in descriptor.network_host):
                raise ValueError("Launch descriptor network host is invalid.")
        else:
            raise ValueError("Launch descriptor has an unsupported transport.")
        if descriptor.backend in {"frida", "frida-trace"} and descriptor.transport != "network":
            raise ValueError("This Frida launch descriptor requires a network endpoint.")
        supported_trace_options = {"-i", "-x", "-I", "-X", "-a", "-T", "-j", "-J"}
        if descriptor.backend != "frida-trace" and descriptor.trace_options:
            raise ValueError("Trace filters are valid only for the Frida Trace backend.")
        for flag, value in descriptor.trace_options:
            if flag not in supported_trace_options or not value.strip():
                raise ValueError("Frida Trace contains an unsupported or empty filter option.")

    def _descriptor_from_command(
        self,
        session_type: InteractiveSessionType,
        serial: str,
        command: Sequence[str],
    ) -> InstrumentationLaunchDescriptor:
        argv = tuple(str(part) for part in command)
        if not argv:
            raise ValueError("the stored command is empty")
        backend = {
            InteractiveSessionType.OBJECTION: "objection",
            InteractiveSessionType.FRIDA_REPL: "frida",
            InteractiveSessionType.FRIDA_TRACE: "frida-trace",
        }.get(session_type)
        if backend is None:
            raise ValueError("the stored backend is unsupported")
        executable_backend = Path(argv[0]).name.casefold()
        if executable_backend.endswith(".exe"):
            executable_backend = executable_backend[:-4]
        if executable_backend != backend:
            raise ValueError("the stored executable does not match the session backend")

        def option(flag: str) -> str:
            try:
                index = argv.index(flag)
                return argv[index + 1]
            except (ValueError, IndexError) as exc:
                raise ValueError(f"the stored command is missing {flag}") from exc

        if backend == "objection":
            target = option("-n")
            mode = "spawn" if "-s" in argv else "attach"
            target_kind = classify_target(target)
            if "-S" in argv:
                usb_serial = option("-S")
                if usb_serial.casefold() in {"usb", "socket", "network"}:
                    raise ValueError("the stored -S value is a transport label, not a USB serial")
                descriptor = InstrumentationLaunchDescriptor(
                    backend, "start", mode, target_kind, target, "usb",
                    serial, usb_serial=usb_serial,
                )
            elif "-N" in argv:
                host = option("-h")
                try:
                    port = int(option("-P"))
                except ValueError as exc:
                    raise ValueError("the stored network port is invalid") from exc
                descriptor = InstrumentationLaunchDescriptor(
                    backend, "start", mode, target_kind, target, "network",
                    serial, network_host=host, network_port=port,
                )
            else:
                raise ValueError("the stored Objection transport is incomplete")
            self._validate_descriptor(descriptor)
            return descriptor

        endpoint = option("-H")
        host, port = self._split_endpoint(endpoint)
        flag = next((value for value in ("-f", "-p", "-N", "-n", "-F") if value in argv), "")
        if not flag:
            raise ValueError("the stored Frida target selector is missing")
        mode, target_kind = {
            "-f": ("spawn", "application"),
            "-p": ("pid", "pid"),
            "-N": ("attach", "application"),
            "-n": ("attach", "name"),
            "-F": ("frontmost", "frontmost"),
        }[flag]
        target = "frontmost" if flag == "-F" else option(flag)
        trace_options = []
        if backend == "frida-trace":
            for index, value in enumerate(argv[:-1]):
                if value in {"-i", "-x", "-I", "-X", "-a", "-T", "-j", "-J"}:
                    trace_options.append((value, argv[index + 1]))
        script_path = option("-l") if "-l" in argv else ""
        descriptor = InstrumentationLaunchDescriptor(
            backend, "trace" if backend == "frida-trace" else "repl",
            mode, target_kind, target, "network", serial,
            network_host=host, network_port=port,
            trace_options=tuple(trace_options), script_path=script_path,
        )
        self._validate_descriptor(descriptor)
        return descriptor

    def refresh_states(self):
        for session_id, process in tuple(self._processes.items()):
            poll = getattr(process, "poll", None)
            returncode = poll() if callable(poll) else None
            if returncode is not None:
                record = self.records.get(session_id)
                if record and record.state in self.ACTIVE:
                    if (
                        returncode
                        and record.session_type is InteractiveSessionType.OBJECTION
                        and self.objection_recovery is not None
                    ):
                        report = self.objection_recovery.analyze(
                            record.serial,
                            record.target,
                            "Objection external terminal exited unexpectedly.",
                            command_history=record.command_history,
                        )
                        self._put(
                            replace(
                                record,
                                state=InteractiveSessionState.DISCONNECTED,
                                last_error=report.message,
                                diagnostics=(
                                    *record.diagnostics,
                                    report.concise(),
                                )[-12:],
                                technical_details=report.technical_details,
                            )
                        )
                    else:
                        self._put(replace(record, state=InteractiveSessionState.EXITED))
                self._processes.pop(session_id, None)
        return self.list()

    def report_objection_failure(
        self,
        session_id: str,
        details: str,
        *,
        command_history: Sequence[str] = (),
    ):
        record = self.records.get(session_id)
        if (
            not record
            or record.session_type is not InteractiveSessionType.OBJECTION
            or self.objection_recovery is None
        ):
            return None
        report = self.objection_recovery.analyze(
            record.serial,
            record.target,
            details,
            command_history=command_history or record.command_history,
        )
        history = tuple(command_history or record.command_history)[-100:]
        self._put(
            replace(
                record,
                state=(
                    InteractiveSessionState.DISCONNECTED
                    if report.kind in self.objection_recovery.CONNECTION_KINDS
                    else InteractiveSessionState.FAILED
                ),
                last_error=report.message,
                diagnostics=(*record.diagnostics, report.concise())[-12:],
                technical_details=report.technical_details,
                command_history=history,
            )
        )
        return report

    def check_objection_connection(self, session_id: str):
        record = self.records.get(session_id)
        if (
            not record
            or record.session_type is not InteractiveSessionType.OBJECTION
            or self.objection_recovery is None
        ):
            return None
        report = self.objection_recovery.check_connection(
            record.serial, record.target
        )
        self._put(
            replace(
                record,
                diagnostics=(*record.diagnostics, report.concise())[-12:],
            )
        )
        return report

    def repair_objection_forwarding(self, session_id: str):
        record = self.records.get(session_id)
        if (
            not record
            or record.session_type is not InteractiveSessionType.OBJECTION
            or self.objection_recovery is None
        ):
            return None
        repair, report = self.objection_recovery.repair_managed_forwarding(
            record.serial, record.target
        )
        self._put(
            replace(
                record,
                diagnostics=(*record.diagnostics, report.concise())[-12:],
            )
        )
        return repair, report

    def interrupt(self, session_id: str) -> SessionOperationResult:
        record = self.records.get(session_id)
        process = self._processes.get(session_id)
        if not record or process is None:
            return SessionOperationResult(False, record, "No tracked terminal process is available to interrupt.")
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        except (AttributeError, OSError) as exc:
            return SessionOperationResult(False, record, str(exc))
        return SessionOperationResult(True, self._put(replace(record, state=InteractiveSessionState.DISCONNECTED)))

    def terminate(self, session_id: str) -> SessionOperationResult:
        record = self.records.get(session_id)
        process = self._processes.pop(session_id, None)
        if not record:
            return SessionOperationResult(False, error="Session record was not found.")
        try:
            if process is not None and callable(getattr(process, "terminate", None)):
                process.terminate()
        except OSError as exc:
            return SessionOperationResult(False, record, str(exc))
        return SessionOperationResult(True, self._put(replace(record, state=InteractiveSessionState.EXITED)))

    def close_record(self, session_id: str) -> SessionOperationResult:
        record = self.records.get(session_id)
        if not record:
            return SessionOperationResult(False, error="Session record was not found.")
        if record.state in self.ACTIVE:
            return SessionOperationResult(False, record, "Terminate the active session before closing its record.")
        with self._lock:
            self.records.pop(session_id, None)
            self._plans.pop(session_id, None)
            self._processes.pop(session_id, None)
        self._changed(record)
        return SessionOperationResult(True, record)

    def diagnostics(self, session_id: str) -> str:
        record = self.records.get(session_id)
        if not record:
            return "Session record was not found."
        descriptor = record.descriptor
        descriptor_lines = (
            (
                "Canonical launch descriptor:",
                f"- Backend: {descriptor.backend}",
                f"- Operation: {descriptor.operation}",
                f"- Mode: {descriptor.mode}",
                f"- Target kind: {descriptor.target_kind}",
                f"- Exact target: {descriptor.target}",
                f"- Transport: {descriptor.transport}",
                f"- USB serial: {descriptor.usb_serial or 'None'}",
                f"- Network host: {descriptor.network_host or 'None'}",
                f"- Network port: {descriptor.network_port or 'None'}",
                f"- Trace options: {descriptor.trace_options or 'None'}",
                f"- Script: {descriptor.script_path or 'None'}",
            )
            if descriptor else ("Canonical launch descriptor: unavailable (legacy record)",)
        )
        lines = (
            f"Session ID: {record.session_id}",
            f"Type: {record.session_type.value}",
            f"Device serial: {record.serial or 'None'}",
            f"Target: {record.target or 'None'}",
            f"Endpoint: {record.endpoint or 'None'}",
            f"State: {record.state.value}",
            f"Backend: {record.backend or 'Not launched'}",
            f"Started: {record.start_time}",
            f"Prompt ready: {record.prompt_ready_time or 'Not observable'}",
            "Launch stages:",
            *(f"- {name}: {value}" for name, value in record.stages),
            f"Command: {SessionLaunchPlan(record.session_type, record.command).preview()}",
            *descriptor_lines,
            f"Last error: {record.last_error or 'None'}",
            f"Command history: {len(record.command_history)} preserved entr{'y' if len(record.command_history) == 1 else 'ies'}",
            *(f"- {entry}" for entry in record.command_history),
            *record.diagnostics,
            *(
                (
                    "Technical Details:",
                    record.technical_details,
                )
                if record.technical_details
                else ()
            ),
        )
        return "\n".join(lines)

    def shutdown(self):
        results = []
        for session_id, record in tuple(self.records.items()):
            if record.state in self.ACTIVE:
                results.append(self.terminate(session_id))
        self._listeners.clear()
        return tuple(results)
