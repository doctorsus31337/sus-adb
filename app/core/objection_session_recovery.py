"""Bounded, selected-device-safe recovery diagnostics for Objection sessions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from app.core.frida_manager import ManagedForwardingRepair


class ObjectionFailureKind(str, Enum):
    DEVICE_GONE = "device-gone"
    TARGET_EXITED = "target-exited"
    ENDPOINT_UNREACHABLE = "endpoint-unreachable"
    FORWARDING_MISSING = "forwarding-missing"
    CLEANUP_DESTROYED = "cleanup-script-destroyed"
    COMMAND_ERROR = "command-error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ObjectionRecoveryReport:
    kind: ObjectionFailureKind
    serial: str
    target: str
    message: str
    possible_causes: tuple[str, ...]
    actions: tuple[str, ...]
    adb_state: str = "unknown"
    endpoint_reachable: bool | None = None
    forwarding_ready: bool | None = None
    managed_forwarding: tuple[str, ...] = ()
    can_repair_managed_forwarding: bool = False
    fresh_session_required: bool = False
    technical_details: str = ""
    command_history: tuple[str, ...] = ()
    repeat_count: int = 1

    def concise(self) -> str:
        causes = "\n".join(f"- {value}" for value in self.possible_causes)
        actions = "  ".join(f"[ {value} ]" for value in self.actions)
        repeated = (
            f"\nRepeated occurrence count: {self.repeat_count}"
            if self.repeat_count > 1 else ""
        )
        return (
            f"{self.message}\n\nPossible causes:\n{causes}\n\n{actions}{repeated}"
        )


class ObjectionSessionRecovery:
    CAUSES = (
        "USB/ADB state changed",
        "application exited or restarted",
        "Frida Server or Gadget stopped",
        "forwarding disappeared",
    )
    CONNECTION_KINDS = frozenset(
        (
            ObjectionFailureKind.DEVICE_GONE,
            ObjectionFailureKind.TARGET_EXITED,
            ObjectionFailureKind.ENDPOINT_UNREACHABLE,
            ObjectionFailureKind.FORWARDING_MISSING,
            ObjectionFailureKind.CLEANUP_DESTROYED,
        )
    )

    def __init__(
        self,
        frida,
        *,
        selected_serial_provider: Callable[[], str | None],
        adb_state_provider: Callable[[str], str] = lambda _serial: "unknown",
        max_technical_chars: int = 20_000,
        history_limit: int = 100,
    ):
        self.frida = frida
        self.selected_serial_provider = selected_serial_provider
        self.adb_state_provider = adb_state_provider
        self.max_technical_chars = max(1_000, int(max_technical_chars))
        self.history_limit = max(1, int(history_limit))
        self._repeats: dict[tuple[str, str, ObjectionFailureKind], int] = {}
        self._details: dict[tuple[str, str, ObjectionFailureKind], str] = {}

    @staticmethod
    def classify(details: str) -> ObjectionFailureKind:
        text = details.casefold()
        if any(
            marker in text
            for marker in (
                "device is gone",
                "device has been disconnected",
                "device disconnected",
                "device not found",
            )
        ):
            return ObjectionFailureKind.DEVICE_GONE
        if any(
            marker in text
            for marker in (
                "process terminated",
                "process exited",
                "unable to find process",
                "process not found",
                "target process has exited",
                "session is detached",
            )
        ):
            return ObjectionFailureKind.TARGET_EXITED
        if any(
            marker in text
            for marker in (
                "forwarding disappeared",
                "forwarding is missing",
                "tcp forwarding is unavailable",
            )
        ):
            return ObjectionFailureKind.FORWARDING_MISSING
        if any(
            marker in text
            for marker in (
                "connection refused",
                "unable to connect",
                "endpoint unreachable",
                "transport endpoint is not connected",
                "frida server is not reachable",
            )
        ):
            return ObjectionFailureKind.ENDPOINT_UNREACHABLE
        if "script is destroyed" in text or "script has been destroyed" in text:
            return ObjectionFailureKind.CLEANUP_DESTROYED
        if any(
            marker in text
            for marker in (
                "unknown command",
                "invalid command",
                "invalid syntax",
                "usage:",
            )
        ):
            return ObjectionFailureKind.COMMAND_ERROR
        return ObjectionFailureKind.UNKNOWN

    def analyze(
        self,
        serial: str,
        target: str,
        details: str,
        *,
        command_history: Sequence[str] = (),
    ) -> ObjectionRecoveryReport:
        kind = self.classify(details)
        key = (serial, target, kind)
        count = self._repeats.get(key, 0) + 1
        self._repeats[key] = count
        if key not in self._details:
            self._details[key] = details[: self.max_technical_chars]
        history = tuple(str(item) for item in command_history)[-self.history_limit :]
        if kind in self.CONNECTION_KINDS:
            message = (
                "Objection lost its connection to the selected device or application."
            )
            actions = (
                "Check Connection",
                "Repair Managed Forwarding",
                "Reconnect",
                "Copy Diagnostics",
            )
        elif kind is ObjectionFailureKind.COMMAND_ERROR:
            message = "Objection rejected the command; the session connection may still be active."
            actions = ("Review Command", "Copy Diagnostics")
        else:
            message = "Objection reported an unexpected session failure."
            actions = ("Check Connection", "Reconnect", "Copy Diagnostics")
        return ObjectionRecoveryReport(
            kind,
            serial,
            target,
            message,
            self.CAUSES if kind in self.CONNECTION_KINDS else ("Invalid command or session error",),
            actions,
            adb_state=self.adb_state_provider(serial),
            managed_forwarding=self.frida.managed_forwarding_ports(serial),
            can_repair_managed_forwarding=bool(
                self.frida.managed_forwarding_ports(serial)
            ),
            fresh_session_required=kind
            in {
                ObjectionFailureKind.DEVICE_GONE,
                ObjectionFailureKind.TARGET_EXITED,
                ObjectionFailureKind.CLEANUP_DESTROYED,
            },
            technical_details=self._details[key],
            command_history=history,
            repeat_count=count,
        )

    def check_connection(self, serial: str, target: str) -> ObjectionRecoveryReport:
        selected = self.selected_serial_provider()
        if not serial or selected != serial:
            return self.analyze(
                serial,
                target,
                "Device disconnected or a different serial is selected.",
            )
        adb_state = self.adb_state_provider(serial)
        if adb_state not in {"device", "recovery", "sideload"}:
            report = self.analyze(serial, target, f"ADB state is {adb_state}. Device is gone.")
            return self._with_probe(report, adb_state, False, False)
        forwarding = self.frida.forwarding_status(serial)
        ready = forwarding.port_27042 and forwarding.port_27043
        if not ready:
            report = self.analyze(serial, target, "Frida forwarding is missing.")
            return self._with_probe(report, adb_state, False, False)
        endpoint = self.frida.list_processes(serial)
        if not endpoint.ok:
            report = self.analyze(
                serial,
                target,
                f"Frida endpoint unreachable. {endpoint.output}",
            )
            return self._with_probe(report, adb_state, False, True)
        return ObjectionRecoveryReport(
            ObjectionFailureKind.UNKNOWN,
            serial,
            target,
            "ADB and the Frida endpoint are reachable. A restarted application still requires a fresh attach or spawn session.",
            ("The original target process may have exited or restarted",),
            ("Reconnect", "Copy Diagnostics"),
            adb_state=adb_state,
            endpoint_reachable=True,
            forwarding_ready=True,
            managed_forwarding=self.frida.managed_forwarding_ports(serial),
            can_repair_managed_forwarding=bool(
                self.frida.managed_forwarding_ports(serial)
            ),
        )

    def repair_managed_forwarding(
        self, serial: str, target: str
    ) -> tuple[ManagedForwardingRepair, ObjectionRecoveryReport]:
        if self.selected_serial_provider() != serial:
            repair = ManagedForwardingRepair(
                serial,
                errors=("Repair requires the same explicitly selected serial.",),
            )
        else:
            repair = self.frida.repair_managed_forwarding(serial)
        details = (
            "Managed forwarding repaired."
            if repair.ok
            else "; ".join(repair.errors) or "Managed forwarding repair failed."
        )
        report = self.check_connection(serial, target) if repair.ok else self.analyze(
            serial, target, details
        )
        return repair, report

    @staticmethod
    def _with_probe(report, adb_state, endpoint_reachable, forwarding_ready):
        return ObjectionRecoveryReport(
            report.kind,
            report.serial,
            report.target,
            report.message,
            report.possible_causes,
            report.actions,
            adb_state,
            endpoint_reachable,
            forwarding_ready,
            report.managed_forwarding,
            report.can_repair_managed_forwarding,
            report.fresh_session_required,
            report.technical_details,
            report.command_history,
            report.repeat_count,
        )
