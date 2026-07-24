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
from app.core.frida_target import FridaTarget


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
        transport: str = "socket",
    ) -> SessionLaunchPlan:
        errors = []
        executable = self._resolve(
            "objection", getattr(self.objection_manager, "objection_path", None)
        )
        if not serial:
            errors.append("Select a device explicitly.")
        if not target.strip():
            errors.append("Select an application or process target.")
        if not executable:
            errors.append(self.resolver.missing_message("objection", "Objection"))
        try:
            builder = (
                self.objection_manager.build_spawn_command
                if spawn else self.objection_manager.build_attach_command
            )
            command = builder(target, transport, serial)
            command = (executable or command[0], *command[1:])
        except (AttributeError, ValueError) as exc:
            command = (executable or "objection",)
            errors.append(str(exc))
        return SessionLaunchPlan(
            InteractiveSessionType.OBJECTION,
            tuple(command),
            serial,
            target,
            "127.0.0.1:27042" if transport == "socket" else serial,
            "spawn" if spawn else "attach",
            executable=executable,
            prerequisites=("Frida route reachable", "Explicit selected target"),
            errors=tuple(dict.fromkeys(errors)),
            explanation="Objection connects in a dedicated terminal and may take time to load its agent.",
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
        command = [executable or tool, "-H", endpoint]
        target_name = ""
        if target is not None:
            if mode == "spawn":
                target_name = target.application_identifier or ""
                if not target_name:
                    errors.append("Spawn requires an application package identifier.")
                command.extend(("-f", target_name))
            elif mode == "pid":
                target_name = str(target.pid or "")
                if not target.pid:
                    errors.append("PID attach requires a running process ID.")
                command.extend(("-p", target_name))
            else:
                target_name = target.identifier or target.name
                if not target_name:
                    errors.append("Attach requires a target name or package.")
                command.extend(("-n", target_name))
        resolved_script = ""
        if script_path:
            path = Path(script_path).expanduser().resolve()
            if not path.is_file():
                errors.append("Select an existing local Frida script.")
            else:
                resolved_script = str(path)
                command.extend(("-l", resolved_script))
        if trace and trace_pattern.strip():
            command.extend(("-i", trace_pattern.strip()))
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
        )

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
            return SessionLaunchPlan(
                InteractiveSessionType.OBJECTION, tuple(command), route_serial,
                route.target or (target.identifier if target and target.identifier else ""),
                "127.0.0.1:27042", "spawn" if "-s" in command else "attach",
                executable=executable, errors=tuple(errors), explanation=route.reason,
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
            return SessionLaunchPlan(
                InteractiveSessionType(route.session_type), tuple(command), route_serial,
                route.target, "127.0.0.1:27042", executable=executable,
                errors=tuple(errors), explanation=route.reason,
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
        plan = self._plans.get(session_id)
        if not record or not plan:
            return SessionOperationResult(False, error="Session record cannot be reconnected.")
        if record.serial and self.selected_serial_provider() != record.serial:
            return SessionOperationResult(False, record, "Reconnect requires the same explicitly selected serial.")
        return self.launch(plan)

    def refresh_states(self):
        for session_id, process in tuple(self._processes.items()):
            poll = getattr(process, "poll", None)
            if callable(poll) and poll() is not None:
                record = self.records.get(session_id)
                if record and record.state in self.ACTIVE:
                    self._put(replace(record, state=InteractiveSessionState.EXITED))
                self._processes.pop(session_id, None)
        return self.list()

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
            f"Last error: {record.last_error or 'None'}",
            *record.diagnostics,
        )
        return "\n".join(lines)

    def shutdown(self):
        results = []
        for session_id, record in tuple(self.records.items()):
            if record.state in self.ACTIVE:
                results.append(self.terminate(session_id))
        self._listeners.clear()
        return tuple(results)
