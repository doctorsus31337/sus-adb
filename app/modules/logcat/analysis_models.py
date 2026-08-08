"""Immutable, GUI-neutral Logcat event analysis models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.modules.logcat.models import LogcatRecord


MAX_UNIQUE_EVENTS = 1_000
MAX_CONTEXT_RECORDS = 100
DEFAULT_CONTEXT_BEFORE = 20
DEFAULT_CONTEXT_AFTER = 30
MAX_STACK_LINES = 200
MAX_EVENT_TITLE = 200
MAX_EVENT_SUMMARY = 1_000
MAX_STACK_LINE = 4_096
MAX_OCCURRENCE_SUMMARIES = 100
MAX_RELEVANT_RECORDS = 300


class LogcatEventKind(str, Enum):
    JAVA_CRASH = "java-crash"
    NATIVE_CRASH = "native-crash"
    ANR = "anr"
    SECURITY_EXCEPTION = "security-exception"
    PERMISSION_DENIAL = "permission-denial"
    SELINUX_DENIAL = "selinux-denial"
    PROCESS_DEATH = "process-death"

    @property
    def label(self) -> str:
        return self.value.replace("-", " ").title()


class LogcatEventSeverity(str, Enum):
    INFORMATION = "information"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return tuple(LogcatEventSeverity).index(self)

    @property
    def label(self) -> str:
        return self.value.title()


class LogcatEventConfidence(str, Enum):
    EXACT = "exact"
    STRONG = "strong"
    HEURISTIC = "heuristic"

    @property
    def label(self) -> str:
        return self.value.title()


@dataclass(frozen=True, slots=True)
class LogcatEventOccurrence:
    first_sequence: int
    last_sequence: int
    first_timestamp_text: str = ""
    last_timestamp_text: str = ""
    summary: str = ""
    relevant_record_sequences: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.first_sequence < 1 or self.last_sequence < self.first_sequence:
            raise ValueError("Occurrence sequence range is invalid.")
        object.__setattr__(self, "summary", str(self.summary)[:MAX_EVENT_SUMMARY])
        object.__setattr__(
            self,
            "relevant_record_sequences",
            tuple(dict.fromkeys(int(value) for value in self.relevant_record_sequences))[
                -MAX_RELEVANT_RECORDS:
            ],
        )


@dataclass(frozen=True, slots=True)
class LogcatEvent:
    event_id: str
    fingerprint: str
    kind: LogcatEventKind
    severity: LogcatEventSeverity
    confidence: LogcatEventConfidence
    title: str
    summary: str
    process: str = ""
    package: str = ""
    pid: int | None = None
    tid: int | None = None
    first_sequence: int = 1
    last_sequence: int = 1
    first_timestamp_text: str = ""
    last_timestamp_text: str = ""
    occurrence_count: int = 1
    context_first_sequence: int = 1
    context_last_sequence: int = 1
    relevant_record_sequences: tuple[int, ...] = ()
    stack_lines: tuple[str, ...] = ()
    detector_id: str = ""
    occurrences: tuple[LogcatEventOccurrence, ...] = ()
    context_records: tuple[LogcatRecord, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", LogcatEventKind(self.kind))
        object.__setattr__(self, "severity", LogcatEventSeverity(self.severity))
        object.__setattr__(self, "confidence", LogcatEventConfidence(self.confidence))
        object.__setattr__(self, "event_id", str(self.event_id)[:96])
        object.__setattr__(self, "fingerprint", str(self.fingerprint)[:128])
        object.__setattr__(self, "title", str(self.title)[:MAX_EVENT_TITLE])
        object.__setattr__(self, "summary", str(self.summary)[:MAX_EVENT_SUMMARY])
        object.__setattr__(self, "process", str(self.process)[:500])
        object.__setattr__(self, "package", str(self.package)[:500])
        object.__setattr__(self, "detector_id", str(self.detector_id)[:200])
        object.__setattr__(
            self,
            "relevant_record_sequences",
            tuple(dict.fromkeys(int(value) for value in self.relevant_record_sequences))[
                -MAX_RELEVANT_RECORDS:
            ],
        )
        object.__setattr__(
            self,
            "stack_lines",
            tuple(str(value)[:MAX_STACK_LINE] for value in self.stack_lines)[
                :MAX_STACK_LINES
            ],
        )
        object.__setattr__(
            self,
            "occurrences",
            tuple(self.occurrences)[-MAX_OCCURRENCE_SUMMARIES:],
        )
        object.__setattr__(
            self,
            "context_records",
            tuple(self.context_records)[-MAX_CONTEXT_RECORDS:],
        )
        if self.first_sequence < 1 or self.last_sequence < self.first_sequence:
            raise ValueError("Event sequence range is invalid.")
        if self.occurrence_count < 1:
            raise ValueError("Event occurrence count starts at one.")
        if self.context_first_sequence < 1:
            raise ValueError("Context sequence range starts at one.")
        if self.context_last_sequence < self.context_first_sequence:
            raise ValueError("Context sequence range is invalid.")


@dataclass(frozen=True, slots=True)
class LogcatAnalysisFilter:
    kind: LogcatEventKind | None = None
    minimum_severity: LogcatEventSeverity = LogcatEventSeverity.INFORMATION
    process_substring: str = ""
    text_search: str = ""

    def __post_init__(self) -> None:
        if self.kind is not None:
            object.__setattr__(self, "kind", LogcatEventKind(self.kind))
        object.__setattr__(
            self, "minimum_severity", LogcatEventSeverity(self.minimum_severity)
        )
        object.__setattr__(self, "process_substring", str(self.process_substring)[:500])
        object.__setattr__(self, "text_search", str(self.text_search)[:500])

    def matches(self, event: LogcatEvent) -> bool:
        if self.kind is not None and event.kind is not self.kind:
            return False
        if event.severity.rank < self.minimum_severity.rank:
            return False
        process_text = f"{event.process} {event.package}".casefold()
        if self.process_substring.casefold() not in process_text:
            return False
        searchable = " ".join(
            (
                event.kind.value,
                event.severity.value,
                event.confidence.value,
                event.title,
                event.summary,
                event.process,
                event.package,
                event.detector_id,
                *event.stack_lines,
            )
        ).casefold()
        return self.text_search.casefold() in searchable


@dataclass(frozen=True, slots=True)
class LogcatAnalysisSnapshot:
    events: tuple[LogcatEvent, ...] = ()
    visible_events: tuple[LogcatEvent, ...] = ()
    dropped_event_groups: int = 0
    filter: LogcatAnalysisFilter = LogcatAnalysisFilter()
    filter_generation: int = 0
    last_processed_sequence: int = 0
    processed_record_count: int = 0
    analysis_latency_ms: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "visible_events", tuple(self.visible_events))
        if self.dropped_event_groups < 0:
            raise ValueError("Dropped-event count cannot be negative.")
        if self.last_processed_sequence < 0 or self.processed_record_count < 0:
            raise ValueError("Analysis counters cannot be negative.")

    @property
    def unique_event_count(self) -> int:
        return len(self.events)

    @property
    def visible_event_count(self) -> int:
        return len(self.visible_events)

    @property
    def total_occurrence_count(self) -> int:
        return sum(event.occurrence_count for event in self.events)
