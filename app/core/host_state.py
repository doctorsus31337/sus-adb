"""Immutable, capability-safe host state observed by trusted plugin APIs."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class DeviceState:
    serial: str
    model: str = "Unknown"
    manufacturer: str = "Unknown"
    state: str = "unknown"
    display_name: str = ""
    root_available: bool = False

    @property
    def authorized(self) -> bool:
        return self.state in {"device", "recovery", "sideload"}

    @property
    def usable(self) -> bool:
        return self.state in {"device", "recovery", "sideload"}

    def to_dict(self) -> dict[str, object]:
        return {
            "serial": self.serial,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "state": self.state,
            "display_name": self.display_name or self.model or self.serial,
            "authorized": self.authorized,
            "usable": self.usable,
            "root_available": self.root_available,
        }


@dataclass(frozen=True, slots=True)
class TargetState:
    name: str = ""
    identifier: str = ""
    pid: int | None = None
    target_type: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "identifier": self.identifier,
            "pid": self.pid,
            "target_type": self.target_type,
        }


@dataclass(frozen=True, slots=True)
class ScopeState:
    scope_id: str = ""
    case_name: str = ""
    authorization_confirmed: bool = False
    allowed_actions: tuple[str, ...] = ()
    excluded_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "scope_id": self.scope_id,
            "case_name": self.case_name,
            "authorization_confirmed": self.authorization_confirmed,
            "allowed_actions": list(self.allowed_actions),
            "excluded_actions": list(self.excluded_actions),
        }


@dataclass(frozen=True, slots=True)
class HostStateSnapshot:
    selected_device: DeviceState | None = None
    devices: tuple[DeviceState, ...] = ()
    adb_state: str = "unavailable"
    selected_target: TargetState | None = None
    assessment_scope: ScopeState | None = None
    session_state: str = "none"
    interface_mode: str = "advanced"
    lifecycle: str = "ready"
    generation: int = 0
    updated_at: str = field(default_factory=_now)

    @property
    def selected_serial(self) -> str:
        return self.selected_device.serial if self.selected_device else ""


class StateSubscription:
    """Idempotent host-owned cancellation handle."""

    def __init__(self, cancel: Callable[[], None]):
        self._cancel = cancel
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            cancel, self._cancel = self._cancel, None
        if cancel:
            cancel()

    close = cancel


class HostStateStore:
    """Thread-safe state store; delivery is delegated to the host UI dispatcher."""

    def __init__(self, dispatcher: Callable[..., None] | None = None):
        self._dispatcher = dispatcher or (lambda callback, *args: callback(*args))
        self._snapshot = HostStateSnapshot()
        self._subscriptions: dict[tuple[str, int], Callable[[HostStateSnapshot], None]] = {}
        self._lock = threading.RLock()

    def snapshot(self) -> HostStateSnapshot:
        with self._lock:
            return self._snapshot

    def publish(self, snapshot: HostStateSnapshot) -> HostStateSnapshot:
        with self._lock:
            if snapshot.generation and snapshot.generation <= self._snapshot.generation:
                return self._snapshot
            current = replace(
                snapshot,
                generation=max(snapshot.generation, self._snapshot.generation + 1),
                updated_at=_now(),
            )
            self._snapshot = current
            callbacks = tuple(self._subscriptions.values())
        for callback in callbacks:
            self._dispatcher(self._deliver, callback, current)
        return current

    @staticmethod
    def _deliver(
        callback: Callable[[HostStateSnapshot], None], snapshot: HostStateSnapshot
    ) -> None:
        callback(snapshot)

    def subscribe(
        self,
        owner: str,
        callback: Callable[[HostStateSnapshot], None],
        *,
        replay: bool = True,
    ) -> StateSubscription:
        key = (str(owner), id(callback))
        with self._lock:
            self._subscriptions[key] = callback
            snapshot = self._snapshot

        if replay:
            self._dispatcher(self._deliver, callback, snapshot)

        def cancel() -> None:
            with self._lock:
                self._subscriptions.pop(key, None)

        return StateSubscription(cancel)

    def unsubscribe_owner(self, owner: str) -> None:
        with self._lock:
            for key in tuple(self._subscriptions):
                if key[0] == owner:
                    self._subscriptions.pop(key, None)

    def subscription_count(self, owner: str | None = None) -> int:
        with self._lock:
            if owner is None:
                return len(self._subscriptions)
            return sum(key[0] == owner for key in self._subscriptions)
