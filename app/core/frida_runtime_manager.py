"""One-target Frida Python runtime supporting multiple loaded agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterable

from app.core.frida_python_adapter import FridaAPIResult, FridaPythonAdapter
from app.core.frida_target import FridaTarget
from app.core.script_descriptor import ScriptDescriptor, ScriptKind, TrustState
from app.core.script_event import ScriptEvent, ScriptEventType
from app.core.script_library import ScriptLibrary
from app.core.script_validator import ScriptValidator


class RuntimeState(str, Enum):
    IDLE = "idle"; CONNECTING = "connecting"; ATTACHED = "attached"
    SPAWNED_PAUSED = "spawned-paused"; ACTIVE = "active"; DETACHING = "detaching"
    DETACHED = "detached"; FAILED = "failed"


@dataclass(slots=True)
class LoadedScript:
    descriptor: ScriptDescriptor
    handle: Any
    loaded_at: str
    state: str = "active"
    latest_digest: str = ""
    rpc_exports: tuple[str, ...] = ()
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    ok: bool
    value: Any = None
    error: str | None = None
    warning: str | None = None


class FridaRuntimeManager:
    def __init__(self, adapter: FridaPythonAdapter, library: ScriptLibrary, validator: ScriptValidator, event_callback: Callable[[ScriptEvent], None] | None = None, diagnosis_provider: Callable[[str], Any] | None = None):
        self.adapter, self.library, self.validator = adapter, library, validator
        self.event_callback = event_callback
        self.diagnosis_provider = diagnosis_provider
        self.last_diagnosis = None
        self.version_warning: str | None = None
        self.state = RuntimeState.IDLE
        self.device = self.session = None
        self.target: FridaTarget | None = None
        self.serial: str | None = None
        self.spawned_pid: int | None = None
        self.loaded: dict[str, LoadedScript] = {}
        self.event_listeners: list[Callable[[ScriptEvent], None]] = []

    def add_event_listener(self, callback):
        if callback not in self.event_listeners: self.event_listeners.append(callback)

    def remove_event_listener(self, callback):
        if callback in self.event_listeners: self.event_listeners.remove(callback)

    def readiness(self, serial: str | None, target: FridaTarget | None) -> RuntimeResult:
        availability = self.adapter.availability()
        errors = []
        if not availability.ok: errors.append(availability.error or "Python Frida is unavailable.")
        if not serial: errors.append("No device is selected.")
        if target is None: errors.append("No target is selected.")
        warning = None
        if serial and self.diagnosis_provider:
            try:
                diagnosis = self.diagnosis_provider(serial)
                self.last_diagnosis = diagnosis
                if not diagnosis.server_running:
                    errors.append("frida-server is not running on the selected device.")
                if not diagnosis.port_27042:
                    errors.append("TCP 27042 forwarding is unavailable.")
                python_version = (availability.value or {}).get("version") if availability.ok else None
                if python_version and diagnosis.server_version and python_version != diagnosis.server_version:
                    warning = f"Python Frida {python_version} does not match device frida-server {diagnosis.server_version}; runtime attachment may be unreliable."
            except Exception as exc:
                errors.append(f"Frida readiness diagnostics failed: {exc}")
        self.version_warning = warning
        return RuntimeResult(not errors, availability.value, "; ".join(errors) or None, warning)

    def attach(self, serial: str | None, target: FridaTarget | None, *, by_pid: bool = False) -> RuntimeResult:
        ready = self.readiness(serial, target)
        if not ready.ok: return ready
        if by_pid and target.pid is None: return RuntimeResult(False, error="The selected target has no PID.")
        self.state = RuntimeState.CONNECTING
        acquired = self.adapter.acquire_device()
        if not acquired.ok: return self._fail(acquired.error)
        identity = target.pid if by_pid else (target.identifier or target.name)
        attached = self.adapter.attach(acquired.value, identity)
        if not attached.ok: return self._fail(attached.error)
        self.device, self.session, self.target, self.serial = acquired.value, attached.value, target, serial
        self.state = RuntimeState.ACTIVE
        self._emit(ScriptEventType.SESSION, f"Attached to {identity}.")
        return RuntimeResult(True, attached.value, warning=ready.warning)

    def spawn(self, serial: str | None, target: FridaTarget | None) -> RuntimeResult:
        ready = self.readiness(serial, target)
        if not ready.ok: return ready
        identifier = target.application_identifier
        if not identifier: return RuntimeResult(False, error="Spawn requires an application identifier.")
        self.state = RuntimeState.CONNECTING
        acquired = self.adapter.acquire_device()
        if not acquired.ok: return self._fail(acquired.error)
        spawned = self.adapter.spawn(acquired.value, identifier)
        if not spawned.ok: return self._fail(spawned.error)
        attached = self.adapter.attach(acquired.value, spawned.value)
        if not attached.ok: return self._fail(attached.error)
        self.device, self.session, self.target, self.serial = acquired.value, attached.value, target, serial
        self.spawned_pid, self.state = spawned.value, RuntimeState.SPAWNED_PAUSED
        self._emit(ScriptEventType.SESSION, f"Spawned {identifier} as PID {spawned.value}; process is paused.")
        return RuntimeResult(True, spawned.value, warning=ready.warning)

    def resume(self) -> RuntimeResult:
        if self.device is None or self.spawned_pid is None: return RuntimeResult(False, error="No spawned process is paused.")
        result = self.adapter.resume(self.device, self.spawned_pid)
        if result.ok:
            self.state = RuntimeState.ACTIVE
            self._emit(ScriptEventType.LIFECYCLE, f"Resumed PID {self.spawned_pid}.")
        return RuntimeResult(result.ok, result.value, result.error)

    def load_script(self, descriptor: ScriptDescriptor, *, confirm_untrusted: bool = False, confirm_state_change: bool = False) -> RuntimeResult:
        if self.session is None or self.state not in {RuntimeState.ACTIVE, RuntimeState.ATTACHED, RuntimeState.SPAWNED_PAUSED}:
            return RuntimeResult(False, error="Attach or spawn a target before loading scripts.")
        if descriptor.script_id in self.loaded:
            return RuntimeResult(True, self.loaded[descriptor.script_id], warning="The script is already loaded.")
        if descriptor.kind is not ScriptKind.FRIDA or descriptor.path.casefold().endswith(".ts"):
            return RuntimeResult(False, error="Only compiled Frida JavaScript files can be loaded.")
        if descriptor.trust is TrustState.UNTRUSTED and not confirm_untrusted:
            return RuntimeResult(False, error="Explicit confirmation is required for an untrusted script.")
        if descriptor.changes_runtime and not confirm_state_change:
            return RuntimeResult(False, error="Explicit confirmation is required for a state-changing script.")
        source = self.library.load_source(descriptor)
        if not source.ok: return RuntimeResult(False, error=source.error)
        validation = self.validator.validate(descriptor, source.text)
        if not validation.valid: return RuntimeResult(False, error="; ".join(validation.errors))
        created = self.adapter.create_script(self.session, source.text or "")
        if not created.ok: return RuntimeResult(False, error=created.error)
        callback = lambda message, data=None, item=descriptor: self._handle_message(item, message, data)
        registered = self.adapter.register_message_callback(created.value, callback)
        if not registered.ok: return RuntimeResult(False, error=registered.error)
        loaded = self.adapter.load_script(created.value)
        if not loaded.ok: return RuntimeResult(False, error=loaded.error)
        exports = self.adapter.list_exports(created.value)
        record = LoadedScript(descriptor, created.value, datetime.now(timezone.utc).isoformat(), latest_digest=descriptor.sha256, rpc_exports=tuple(exports.value or ()))
        self.loaded[descriptor.script_id] = record
        self._emit(ScriptEventType.SCRIPT_LOADED, "Script loaded.", descriptor)
        return RuntimeResult(True, record, warning="; ".join(validation.warnings) if validation.warnings else None)

    def load_multiple(self, descriptors: Iterable[ScriptDescriptor], **confirmations) -> tuple[RuntimeResult, ...]:
        return tuple(self.load_script(item, **confirmations) for item in descriptors)

    def unload_script(self, script_id: str) -> RuntimeResult:
        record = self.loaded.get(script_id)
        if record is None: return RuntimeResult(True, warning="The script is not loaded.")
        result = self.adapter.unload_script(record.handle)
        if result.ok:
            self.loaded.pop(script_id, None)
            record.state = "unloaded"
            self._emit(ScriptEventType.SCRIPT_UNLOADED, "Script unloaded.", record.descriptor)
        return RuntimeResult(result.ok, error=result.error)

    def unload_all(self) -> tuple[RuntimeResult, ...]:
        return tuple(self.unload_script(script_id) for script_id in tuple(self.loaded))

    def reload_script(self, script_id: str, **confirmations) -> RuntimeResult:
        record = self.loaded.get(script_id)
        if record is None: return RuntimeResult(False, error="The script is not loaded.")
        descriptor = record.descriptor
        unloaded = self.unload_script(script_id)
        return self.load_script(descriptor, **confirmations) if unloaded.ok else unloaded

    def reload_all(self, **confirmations) -> tuple[RuntimeResult, ...]:
        ids = tuple(self.loaded)
        return tuple(self.reload_script(script_id, **confirmations) for script_id in ids)

    def list_loaded(self) -> tuple[LoadedScript, ...]: return tuple(self.loaded.values())

    def post(self, script_id: str, message: Any, data: bytes | None = None) -> RuntimeResult:
        record = self.loaded.get(script_id)
        if not record: return RuntimeResult(False, error="The selected script is not loaded.")
        result = self.adapter.post(record.handle, message, data)
        return RuntimeResult(result.ok, error=result.error)

    def list_rpc_exports(self, script_id: str) -> RuntimeResult:
        record = self.loaded.get(script_id)
        if not record: return RuntimeResult(False, error="The selected script is not loaded.")
        result = self.adapter.list_exports(record.handle)
        if result.ok: record.rpc_exports = tuple(result.value or ())
        return RuntimeResult(result.ok, record.rpc_exports if result.ok else None, result.error)

    def call_rpc(self, script_id: str, name: str, args=()) -> RuntimeResult:
        record = self.loaded.get(script_id)
        if not record: return RuntimeResult(False, error="The selected script is not loaded.")
        result = self.adapter.call_export(record.handle, name, args)
        self._emit(ScriptEventType.RPC_RESULT if result.ok else ScriptEventType.RPC_ERROR, f"RPC {name}: {result.value if result.ok else result.error}", record.descriptor, payload={"result": result.value} if result.ok else {})
        return RuntimeResult(result.ok, result.value, result.error)

    def detach(self) -> RuntimeResult:
        self.state = RuntimeState.DETACHING
        self.unload_all()
        result = self.adapter.detach(self.session) if self.session is not None else FridaAPIResult(True)
        self.device = self.session = self.target = None; self.serial = None; self.spawned_pid = None
        self.state = RuntimeState.DETACHED
        self._emit(ScriptEventType.SESSION, "Session detached.")
        return RuntimeResult(result.ok, error=result.error)

    def device_disconnected(self):
        result = self.detach()
        self._emit(ScriptEventType.WARNING, "Selected device disconnected; runtime cleaned up.", severity="warning")
        return result

    def _handle_message(self, descriptor: ScriptDescriptor, message: Any, data: bytes | None):
        try:
            payload = message if isinstance(message, dict) else {"message": message}
            kind = payload.get("type", "send")
            if kind == "error":
                self._emit(ScriptEventType.ERROR, payload.get("description", "Script runtime error"), descriptor, payload=payload, source_file=payload.get("fileName"), source_line=payload.get("lineNumber"), stack_trace=payload.get("stack"), severity="error")
            elif data is not None:
                self._emit(ScriptEventType.BINARY, f"Received {len(data)} binary bytes.", descriptor, payload=payload, binary=data)
            else:
                self._emit(ScriptEventType.SEND, str(payload.get("payload", payload)), descriptor, payload=payload)
        except Exception:
            return

    def _fail(self, error: str | None) -> RuntimeResult:
        self.state = RuntimeState.FAILED
        self._emit(ScriptEventType.ERROR, error or "Frida runtime operation failed.", severity="error")
        return RuntimeResult(False, error=error)

    def _emit(self, event_type, summary, descriptor=None, **kwargs):
        event = ScriptEvent(event_type, summary, script_id=descriptor.script_id if descriptor else None, script_name=descriptor.name if descriptor else None, **kwargs)
        for callback in tuple(([self.event_callback] if self.event_callback else []) + self.event_listeners):
            try: callback(event)
            except Exception: continue
