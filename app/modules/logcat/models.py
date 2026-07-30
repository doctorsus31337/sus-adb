"""Immutable Logcat records, filters, states, and snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


MAX_RAW_LINE = 16_384
DEFAULT_CAPACITY = 10_000
MIN_CAPACITY = 1_000
MAX_CAPACITY = 50_000
MAX_STATUS_TEXT = 500


class LogcatPriority(str, Enum):
    VERBOSE = "V"
    DEBUG = "D"
    INFO = "I"
    WARN = "W"
    ERROR = "E"
    FATAL = "F"

    @property
    def label(self) -> str:
        return {
            self.VERBOSE: "Verbose",
            self.DEBUG: "Debug",
            self.INFO: "Info",
            self.WARN: "Warn",
            self.ERROR: "Error",
            self.FATAL: "Fatal",
        }[self]

    @property
    def rank(self) -> int:
        return tuple(LogcatPriority).index(self)

    @classmethod
    def from_value(cls, value: str | "LogcatPriority") -> "LogcatPriority":
        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip()
        for priority in cls:
            if normalized.casefold() in {
                priority.value.casefold(),
                priority.label.casefold(),
            }:
                return priority
        raise ValueError(f"Unsupported Logcat priority: {value}")


class LogcatCaptureState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    VIEW_PAUSED = "view-paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class LogcatRecord:
    sequence: int
    device_timestamp: str = ""
    pid: int | None = None
    tid: int | None = None
    priority: LogcatPriority | None = None
    tag: str = ""
    message: str = ""
    raw_line: str = ""
    parse_status: str = "malformed"
    continuation_of: int | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("Logcat sequence numbers start at one.")
        if len(self.raw_line) > MAX_RAW_LINE:
            raise ValueError("Logcat raw line exceeds the supported bound.")
        if self.pid is not None and self.pid < 0:
            raise ValueError("PID cannot be negative.")
        if self.tid is not None and self.tid < 0:
            raise ValueError("TID cannot be negative.")

    def display_line(self) -> str:
        if self.parse_status.startswith("parsed"):
            return (
                f"{self.device_timestamp} {self.pid:5d} {self.tid:5d} "
                f"{self.priority.value} {self.tag}: {self.message}"
            )
        if self.parse_status == "continuation":
            return self.raw_line
        return self.raw_line


@dataclass(frozen=True, slots=True)
class LogcatFilter:
    minimum_priority: LogcatPriority = LogcatPriority.VERBOSE
    tag_substring: str = ""
    pid: int | None = None
    message_substring: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "minimum_priority", LogcatPriority.from_value(self.minimum_priority)
        )
        if self.pid is not None and (isinstance(self.pid, bool) or int(self.pid) < 0):
            raise ValueError("PID must be a non-negative integer.")
        if self.pid is not None:
            object.__setattr__(self, "pid", int(self.pid))

    def matches(self, record: LogcatRecord) -> bool:
        if (
            record.priority is not None
            and record.priority.rank < self.minimum_priority.rank
        ):
            return False
        if record.priority is None and self.minimum_priority is not LogcatPriority.VERBOSE:
            return False
        if self.pid is not None and record.pid != self.pid:
            return False
        if self.tag_substring.casefold() not in record.tag.casefold():
            return False
        if self.message_substring.casefold() not in record.message.casefold():
            return False
        return True


@dataclass(frozen=True, slots=True)
class LogcatCaptureSnapshot:
    state: LogcatCaptureState = LogcatCaptureState.IDLE
    selected_serial: str = ""
    capture_serial: str = ""
    records: tuple[LogcatRecord, ...] = ()
    visible_records: tuple[LogcatRecord, ...] = ()
    dropped_records: int = 0
    status_text: str = ""
    error_text: str = ""
    filter: LogcatFilter = LogcatFilter()
    filter_generation: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", LogcatCaptureState(self.state))
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "visible_records", tuple(self.visible_records))
        object.__setattr__(self, "status_text", str(self.status_text)[:MAX_STATUS_TEXT])
        object.__setattr__(self, "error_text", str(self.error_text)[:MAX_STATUS_TEXT])
        if self.dropped_records < 0:
            raise ValueError("Dropped-record count cannot be negative.")

    @property
    def buffered_count(self) -> int:
        return len(self.records)

    @property
    def visible_count(self) -> int:
        return len(self.visible_records)
