"""Optional, dependency-injected adapter for Frida's Python API."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

from app.core.frida_session_manager import FridaSessionManager


@dataclass(frozen=True, slots=True)
class FridaAPIResult:
    ok: bool
    value: Any = None
    error_code: str | None = None
    error: str | None = None


class FridaPythonAdapter:
    def __init__(self, provider: Callable[[], Any] | None = None, endpoint: str = FridaSessionManager.ENDPOINT):
        self.provider = provider or self._import_frida
        self.endpoint = endpoint
        self._module: Any = None
        self._import_attempted = False

    @staticmethod
    def _import_frida():
        return importlib.import_module("frida")

    def _get_module(self) -> FridaAPIResult:
        if not self._import_attempted:
            self._import_attempted = True
            try:
                self._module = self.provider()
            except (ImportError, ModuleNotFoundError) as exc:
                return FridaAPIResult(False, error_code="module-missing", error=f"Python Frida module is unavailable: {exc}")
            except Exception as exc:
                return FridaAPIResult(False, error_code="module-incompatible", error=f"Python Frida module could not be initialized: {exc}")
        if self._module is None:
            return FridaAPIResult(False, error_code="module-missing", error="Python Frida module is unavailable.")
        return FridaAPIResult(True, self._module)

    def availability(self) -> FridaAPIResult:
        result = self._get_module()
        if not result.ok:
            return result
        return FridaAPIResult(True, {"installed": True, "version": str(getattr(result.value, "__version__", "unknown"))})

    def acquire_device(self) -> FridaAPIResult:
        module = self._get_module()
        if not module.ok:
            return module
        try:
            manager = module.value.get_device_manager()
            return FridaAPIResult(True, manager.add_remote_device(self.endpoint))
        except Exception as exc:
            return self._failure(exc, "server-unavailable", "Could not reach frida-server at the selected forwarded endpoint")

    def attach(self, device: Any, target: int | str) -> FridaAPIResult:
        if not target:
            return FridaAPIResult(False, error_code="target-missing", error="A PID, process name, or application identifier is required.")
        try:
            return FridaAPIResult(True, device.attach(target))
        except Exception as exc:
            return self._failure(exc, "attach-failed", f"Could not attach to {target}")

    def spawn(self, device: Any, identifier: str) -> FridaAPIResult:
        if not identifier:
            return FridaAPIResult(False, error_code="target-missing", error="An application identifier is required for spawn.")
        try:
            return FridaAPIResult(True, int(device.spawn([identifier])))
        except Exception as exc:
            return self._failure(exc, "spawn-failed", f"Could not spawn {identifier}")

    def resume(self, device: Any, pid: int) -> FridaAPIResult:
        try:
            device.resume(pid)
            return FridaAPIResult(True, pid)
        except Exception as exc:
            return self._failure(exc, "resume-failed", f"Could not resume PID {pid}")

    def detach(self, session: Any) -> FridaAPIResult:
        try:
            session.detach()
            return FridaAPIResult(True)
        except Exception as exc:
            return self._failure(exc, "session-detached", "Could not detach the Frida session")

    def create_script(self, session: Any, source: str) -> FridaAPIResult:
        try:
            return FridaAPIResult(True, session.create_script(source))
        except Exception as exc:
            return self._failure(exc, "script-compile-error", "Frida could not compile the script")

    def register_message_callback(self, script: Any, callback) -> FridaAPIResult:
        try:
            script.on("message", callback)
            return FridaAPIResult(True)
        except Exception as exc:
            return self._failure(exc, "callback-error", "Could not register the script message callback")

    def load_script(self, script: Any) -> FridaAPIResult:
        try:
            script.load()
            return FridaAPIResult(True, script)
        except Exception as exc:
            return self._failure(exc, "script-load-error", "Frida could not load the script")

    def unload_script(self, script: Any) -> FridaAPIResult:
        try:
            script.unload()
            return FridaAPIResult(True)
        except Exception as exc:
            return self._failure(exc, "script-unload-error", "Frida could not unload the script")

    def post(self, script: Any, message: Any, data: bytes | None = None) -> FridaAPIResult:
        try:
            script.post(message, data=data) if data is not None else script.post(message)
            return FridaAPIResult(True)
        except Exception as exc:
            return self._failure(exc, "post-error", "Could not post the message")

    def list_exports(self, script: Any) -> FridaAPIResult:
        try:
            exports = getattr(script, "exports_sync", None) or getattr(script, "exports", None)
            if exports is None:
                return FridaAPIResult(True, ())
            names = tuple(name for name in dir(exports) if not name.startswith("_"))
            return FridaAPIResult(True, names)
        except Exception as exc:
            return self._failure(exc, "rpc-error", "Could not enumerate RPC exports")

    def call_export(self, script: Any, name: str, args: list[Any] | tuple[Any, ...] = ()) -> FridaAPIResult:
        try:
            exports = getattr(script, "exports_sync", None) or getattr(script, "exports", None)
            method = getattr(exports, name, None) if exports is not None else None
            if not callable(method):
                return FridaAPIResult(False, error_code="rpc-export-missing", error=f"RPC export '{name}' was not found.")
            return FridaAPIResult(True, method(*args))
        except Exception as exc:
            return self._failure(exc, "rpc-error", f"RPC export '{name}' failed")

    @staticmethod
    def _failure(exc: Exception, code: str, context: str) -> FridaAPIResult:
        name = exc.__class__.__name__.casefold()
        mapped = code
        if "processnotfound" in name:
            mapped = "target-not-found"
        elif "servernotrunning" in name or "transport" in name:
            mapped = "server-unavailable"
        elif "invalidoperation" in name:
            mapped = "session-detached"
        return FridaAPIResult(False, error_code=mapped, error=f"{context}: {exc}")
