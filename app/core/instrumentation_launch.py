"""Canonical immutable state and target classification for instrumentation launches."""

from __future__ import annotations

from dataclasses import dataclass


def is_application_identifier(value: str) -> bool:
    parts = value.split(".")
    return len(parts) >= 2 and all(
        part and (part[0].isalpha() or part[0] == "_")
        and all(character.isalnum() or character == "_" for character in part)
        for part in parts
    )


def classify_target(value: str) -> str:
    if value.isdecimal():
        return "pid"
    if is_application_identifier(value):
        return "application"
    return "name"


def normalize_transport(value: str) -> str:
    normalized = value.strip().casefold()
    return "network" if normalized == "socket" else normalized


@dataclass(frozen=True, slots=True)
class InstrumentationLaunchDescriptor:
    """All immutable values required to validate and reproduce one launch."""

    backend: str
    operation: str
    mode: str
    target_kind: str
    target: str
    transport: str
    device_serial: str = ""
    usb_serial: str = ""
    network_host: str = ""
    network_port: int = 0
    trace_options: tuple[tuple[str, str], ...] = ()
    script_path: str = ""

    @property
    def endpoint(self) -> str:
        if self.transport == "usb":
            return self.usb_serial
        if self.transport == "network" and self.network_host and self.network_port:
            return f"{self.network_host}:{self.network_port}"
        return ""
