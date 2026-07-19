"""Immutable structured events emitted by the Frida runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class ScriptEventType(str, Enum):
    SESSION = "session"
    SCRIPT_LOADED = "script-loaded"
    SCRIPT_UNLOADED = "script-unloaded"
    SEND = "send"
    CONSOLE = "console"
    ERROR = "error"
    BINARY = "binary"
    RPC_RESULT = "rpc-result"
    RPC_ERROR = "rpc-error"
    WARNING = "warning"
    LIFECYCLE = "lifecycle"


@dataclass(frozen=True, slots=True)
class ScriptEvent:
    event_type: ScriptEventType
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    script_id: str | None = None
    script_name: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    binary: bytes | None = None
    source_file: str | None = None
    source_line: int | None = None
    stack_trace: str | None = None
    severity: str = "info"

    def __post_init__(self):
        object.__setattr__(self, "event_type", ScriptEventType(self.event_type))
        object.__setattr__(self, "payload", dict(self.payload))

    @property
    def display_text(self) -> str:
        location = f" ({self.source_file or 'script'}:{self.source_line})" if self.source_line else ""
        return f"[{self.timestamp}] {self.event_type.value.upper()} {self.script_name or ''}: {self.summary}{location}".replace("  ", " ")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp, "event_type": self.event_type.value,
            "script_id": self.script_id, "script_name": self.script_name,
            "summary": self.summary, "payload": dict(self.payload),
            "binary_size": len(self.binary) if self.binary is not None else None,
            "source_file": self.source_file, "source_line": self.source_line,
            "stack_trace": self.stack_trace, "severity": self.severity,
            "display_text": self.display_text,
        }
