"""GUI-independent model for a discoverable Frida target."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TargetType(str, Enum):
    APPLICATION = "application"
    PROCESS = "process"


@dataclass(frozen=True, slots=True)
class FridaTarget:
    name: str
    identifier: str | None
    pid: int | None
    target_type: TargetType
    running: bool
    display_label: str = field(init=False)

    def __post_init__(self):
        name = self.name.strip()
        identifier = self.identifier.strip() if self.identifier else None
        if self.pid is not None and (not isinstance(self.pid, int) or self.pid <= 0):
            raise ValueError("A target PID must be a positive integer.")
        if not isinstance(self.target_type, TargetType):
            object.__setattr__(self, "target_type", TargetType(self.target_type))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "identifier", identifier)
        primary = name or identifier or "Unnamed target"
        details = [self.target_type.value.title()]
        if identifier and identifier != primary:
            details.append(identifier)
        if self.pid is not None:
            details.append(f"PID {self.pid}")
        object.__setattr__(self, "display_label", f"{primary} — {' · '.join(details)}")

    @property
    def application_identifier(self) -> str | None:
        return self.identifier if self.target_type is TargetType.APPLICATION else None
