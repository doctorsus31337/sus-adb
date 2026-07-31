"""Deterministic, bounded detectors for parsed Android Logcat records."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.modules.logcat.analysis_models import (
    MAX_EVENT_SUMMARY,
    MAX_EVENT_TITLE,
    MAX_STACK_LINE,
    MAX_STACK_LINES,
    LogcatEventConfidence,
    LogcatEventKind,
    LogcatEventSeverity,
)
from app.modules.logcat.models import LogcatPriority, LogcatRecord


_WHITESPACE = re.compile(r"\s+")
_HEX_ADDRESS = re.compile(r"(?<![\w])(?:0x)?[0-9a-fA-F]{8,16}(?![\w])")
_JAVA_LINE_NUMBER = re.compile(r"(?<=\.java):\d+")
_OBJECT_ID = re.compile(r"@[0-9a-fA-F]{6,}")
_NATIVE_OFFSET = re.compile(r"\+\s*0x[0-9a-fA-F]+")
_JAVA_EXCEPTION = re.compile(
    r"^(?:(?:Caused by|Suppressed):\s*)?"
    r"(?P<class>[\w.$]+(?:Exception|Error|Throwable))"
    r"(?::\s*(?P<message>.*))?$"
)
_JAVA_PROCESS = re.compile(
    r"\bProcess:\s*(?P<process>[^,]+),\s*PID:\s*(?P<pid>\d+)"
)
_NATIVE_SIGNAL = re.compile(
    r"\bFatal signal\s+(?P<number>\d+)\s+\((?P<signal>[^)]+)\)"
    r".*?\bpid\s+(?P<pid>\d+)(?:\s+\([^)]*\))?"
    r"(?:,\s*tid\s+(?P<tid>\d+))?",
    re.IGNORECASE,
)
_NATIVE_PROCESS = re.compile(r">>>\s*(?P<process>[^<]+?)\s*<<<")
_NATIVE_FRAME = re.compile(r"^\s*#\d+\s+pc\s+", re.IGNORECASE)
_ANR_PROCESS = re.compile(r"\bANR in\s+(?P<process>[^\s,]+)", re.IGNORECASE)
_ANR_REASON = re.compile(r"\bReason:\s*(?P<reason>.+)$", re.IGNORECASE)
_PERMISSION_NAME = re.compile(r"\bandroid\.permission\.[A-Z0-9_.]+")
_SELINUX_FIELD = {
    "source": re.compile(r"\bscontext=(?P<value>\S+)"),
    "target": re.compile(r"\btcontext=(?P<value>\S+)"),
    "class": re.compile(r"\btclass=(?P<value>\S+)"),
    "command": re.compile(r'\bcomm="(?P<value>[^"]+)"'),
}
_SELINUX_PERMISSION = re.compile(r"avc:\s*denied\s*\{\s*(?P<value>[^}]+)\s*\}")
_PROCESS_DIED = re.compile(
    r"\bProcess\s+(?P<process>[\w.:/-]+)\s+\(pid\s+(?P<pid>\d+)\)"
    r"\s+has died\b",
    re.IGNORECASE,
)
_PROCESS_KILLING = re.compile(
    r"\bKilling\s+(?P<pid>\d+):(?P<process>[\w.:/-]+)/\S+"
    r"\s+\([^)]*\):\s+.+$",
    re.IGNORECASE,
)


def _message(record: LogcatRecord) -> str:
    return str(record.message or record.raw_line)


def normalize_fingerprint_text(value: str) -> str:
    """Remove only known volatile identifiers while preserving semantic names."""

    normalized = _HEX_ADDRESS.sub("<addr>", str(value))
    normalized = _OBJECT_ID.sub("@<object>", normalized)
    normalized = _JAVA_LINE_NUMBER.sub(":<line>", normalized)
    normalized = _NATIVE_OFFSET.sub("+ <offset>", normalized)
    return _WHITESPACE.sub(" ", normalized).strip().casefold()


def stable_fingerprint(*parts: object) -> str:
    normalized = "\x1f".join(normalize_fingerprint_text(str(part)) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DetectedLogcatEvent:
    occurrence_key: str
    fingerprint: str
    kind: LogcatEventKind
    severity: LogcatEventSeverity
    confidence: LogcatEventConfidence
    title: str
    summary: str
    process: str
    package: str
    pid: int | None
    tid: int | None
    first_sequence: int
    last_sequence: int
    first_timestamp_text: str
    last_timestamp_text: str
    relevant_record_sequences: tuple[int, ...]
    stack_lines: tuple[str, ...]
    detector_id: str
    complete: bool = True


@dataclass(slots=True)
class _Candidate:
    kind: LogcatEventKind
    detector_id: str
    start: LogcatRecord
    records: list[LogcatRecord] = field(default_factory=list)
    process: str = ""
    pid: int | None = None
    tid: int | None = None
    exception_class: str = ""
    exception_message: str = ""
    signal: str = ""
    abort_message: str = ""
    reason: str = ""
    stack_lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.records.append(self.start)
        self.pid = self.start.pid
        self.tid = self.start.tid

    @property
    def occurrence_key(self) -> str:
        return f"{self.kind.value}:{self.start.sequence}"


class LogcatDetectorEngine:
    """Incremental state machine; it never executes or evaluates message content."""

    def __init__(self) -> None:
        self._candidate: _Candidate | None = None
        self._recent_crash_pids: dict[int, int] = {}

    def reset(self) -> None:
        self._candidate = None
        self._recent_crash_pids.clear()

    @staticmethod
    def _is_java_start(record: LogcatRecord) -> bool:
        return (
            record.tag.casefold() == "androidruntime"
            and record.priority in {LogcatPriority.ERROR, LogcatPriority.FATAL}
            and _message(record).lstrip().startswith("FATAL EXCEPTION:")
        )

    @staticmethod
    def _is_native_start(record: LogcatRecord) -> bool:
        text = _message(record).casefold()
        return bool(
            _NATIVE_SIGNAL.search(_message(record))
            or (
                record.tag.casefold()
                in {
                    "tombstoned",
                    "crash_dump",
                    "crash_dump32",
                    "crash_dump64",
                }
                and (
                    "received crash request" in text
                    or "performing dump of process" in text
                )
            )
        )

    @staticmethod
    def _is_anr_start(record: LogcatRecord) -> bool:
        text = _message(record)
        tag = record.tag.casefold()
        return bool(
            _ANR_PROCESS.search(text)
            or (
                "input dispatching timed out" in text.casefold()
                and tag
                in {
                    "activitymanager",
                    "activitytaskmanager",
                    "windowmanager",
                    "inputdispatcher",
                }
            )
        )

    @staticmethod
    def _candidate_associated(candidate: _Candidate, record: LogcatRecord) -> bool:
        text = _message(record).strip()
        if record.sequence - candidate.start.sequence > MAX_STACK_LINES + 80:
            return False
        if record.continuation_of in {value.sequence for value in candidate.records[-8:]}:
            return True
        if candidate.kind is LogcatEventKind.JAVA_CRASH:
            if record.tag.casefold() != "androidruntime":
                return False
            return bool(
                _JAVA_PROCESS.search(text)
                or _JAVA_EXCEPTION.search(text)
                or text.startswith(("at ", "Caused by:", "Suppressed:", "... "))
                or not text
            )
        if candidate.kind is LogcatEventKind.NATIVE_CRASH:
            if record.tag.casefold() not in {
                "debug",
                "libc",
                "tombstoned",
                "crash_dump",
                "crash_dump32",
                "crash_dump64",
            }:
                return False
            folded = text.casefold()
            return bool(
                _NATIVE_FRAME.search(text)
                or _NATIVE_PROCESS.search(text)
                or folded.startswith(("abort message:", "backtrace:", "signal "))
                or not text
            )
        if candidate.kind is LogcatEventKind.ANR:
            return (
                record.tag.casefold()
                in {"activitymanager", "activitytaskmanager", "windowmanager"}
                and bool(
                    _ANR_REASON.search(text)
                    or text.casefold().startswith(("load:", "cpu usage", "reason:"))
                )
                and record.sequence - candidate.start.sequence <= 8
            )
        return False

    @staticmethod
    def _append_candidate(candidate: _Candidate, record: LogcatRecord) -> None:
        candidate.records.append(record)
        text = _message(record).strip()
        if candidate.kind is LogcatEventKind.JAVA_CRASH:
            process = _JAVA_PROCESS.search(text)
            if process:
                candidate.process = process.group("process").strip()
                candidate.pid = int(process.group("pid"))
            exception = _JAVA_EXCEPTION.match(text)
            if exception and not text.startswith(("Caused by:", "Suppressed:")):
                if not candidate.exception_class:
                    candidate.exception_class = exception.group("class")
                    candidate.exception_message = exception.group("message") or ""
            if text.startswith(("at ", "Caused by:", "Suppressed:", "... ")):
                candidate.stack_lines.append(text[:MAX_STACK_LINE])
        elif candidate.kind is LogcatEventKind.NATIVE_CRASH:
            process = _NATIVE_PROCESS.search(text)
            if process:
                candidate.process = process.group("process").strip()
            if text.casefold().startswith("abort message:"):
                candidate.abort_message = text.split(":", 1)[1].strip().strip("'\"")
            if _NATIVE_FRAME.search(text):
                candidate.stack_lines.append(text[:MAX_STACK_LINE])
        elif candidate.kind is LogcatEventKind.ANR:
            reason = _ANR_REASON.search(text)
            if reason:
                candidate.reason = reason.group("reason").strip()

    @staticmethod
    def _candidate_ready(candidate: _Candidate) -> bool:
        if candidate.kind is LogcatEventKind.JAVA_CRASH:
            return bool(candidate.exception_class and candidate.stack_lines)
        if candidate.kind is LogcatEventKind.NATIVE_CRASH:
            return bool(candidate.signal and candidate.stack_lines)
        return candidate.kind is LogcatEventKind.ANR

    def _candidate_draft(
        self, candidate: _Candidate, *, complete: bool
    ) -> DetectedLogcatEvent:
        last = candidate.records[-1]
        if candidate.kind is LogcatEventKind.JAVA_CRASH:
            identity = candidate.process or (
                f"pid:{candidate.pid}" if candidate.pid is not None else candidate.start.tag
            )
            top_frame = next(
                (line for line in candidate.stack_lines if line.startswith("at ")), ""
            )
            fingerprint = stable_fingerprint(
                candidate.kind.value,
                identity,
                candidate.exception_class or "unknown-java-exception",
                top_frame,
            )
            title = (
                f"Java crash: {candidate.exception_class}"
                if candidate.exception_class
                else "Java runtime crash"
            )
            summary = candidate.exception_message or _message(candidate.start)
            confidence = (
                LogcatEventConfidence.EXACT
                if candidate.process and candidate.exception_class and top_frame
                else LogcatEventConfidence.STRONG
            )
            severity = LogcatEventSeverity.CRITICAL
        elif candidate.kind is LogcatEventKind.NATIVE_CRASH:
            identity = candidate.process or (
                f"pid:{candidate.pid}" if candidate.pid is not None else candidate.start.tag
            )
            top_frame = candidate.stack_lines[0] if candidate.stack_lines else ""
            fingerprint = stable_fingerprint(
                candidate.kind.value, identity, candidate.signal, top_frame
            )
            title = f"Native crash: {candidate.signal or 'fatal signal'}"
            summary = candidate.abort_message or _message(candidate.start)
            confidence = (
                LogcatEventConfidence.EXACT
                if candidate.signal and candidate.stack_lines
                else LogcatEventConfidence.STRONG
            )
            severity = LogcatEventSeverity.CRITICAL
        else:
            identity = candidate.process or (
                f"pid:{candidate.pid}" if candidate.pid is not None else candidate.start.tag
            )
            fingerprint = stable_fingerprint(
                candidate.kind.value, identity, _message(candidate.start)
            )
            title = f"ANR: {candidate.process or 'application not responding'}"
            summary = candidate.reason or _message(candidate.start)
            confidence = LogcatEventConfidence.EXACT
            severity = LogcatEventSeverity.ERROR
        return DetectedLogcatEvent(
            candidate.occurrence_key,
            fingerprint,
            candidate.kind,
            severity,
            confidence,
            title[:MAX_EVENT_TITLE],
            summary[:MAX_EVENT_SUMMARY],
            candidate.process,
            candidate.process,
            candidate.pid,
            candidate.tid,
            candidate.start.sequence,
            last.sequence,
            candidate.start.device_timestamp,
            last.device_timestamp or candidate.start.device_timestamp,
            tuple(value.sequence for value in candidate.records),
            tuple(candidate.stack_lines[:MAX_STACK_LINES]),
            candidate.detector_id,
            complete,
        )

    @staticmethod
    def _point_event(
        record: LogcatRecord,
        *,
        kind: LogcatEventKind,
        severity: LogcatEventSeverity,
        confidence: LogcatEventConfidence,
        title: str,
        summary: str,
        detector_id: str,
        process: str = "",
        pid: int | None = None,
        fingerprint_parts: tuple[object, ...] = (),
    ) -> DetectedLogcatEvent:
        identity = process or (
            f"pid:{record.pid}" if record.pid is not None else record.tag
        )
        fingerprint = stable_fingerprint(kind.value, identity, *fingerprint_parts)
        return DetectedLogcatEvent(
            f"{kind.value}:{record.sequence}",
            fingerprint,
            kind,
            severity,
            confidence,
            title[:MAX_EVENT_TITLE],
            summary[:MAX_EVENT_SUMMARY],
            process,
            process,
            record.pid if pid is None else pid,
            record.tid,
            record.sequence,
            record.sequence,
            record.device_timestamp,
            record.device_timestamp,
            (record.sequence,),
            (),
            detector_id,
            True,
        )

    def _detect_point(self, record: LogcatRecord) -> tuple[DetectedLogcatEvent, ...]:
        text = _message(record)
        folded = text.casefold()
        results: list[DetectedLogcatEvent] = []
        if "avc: denied" in folded:
            fields = {}
            for name, pattern in _SELINUX_FIELD.items():
                match = pattern.search(text)
                if match:
                    fields[name] = match.group("value")
            permission = _SELINUX_PERMISSION.search(text)
            requested = permission.group("value").strip() if permission else ""
            process = fields.get("command", "")
            useful = ", ".join(
                f"{name}={value}"
                for name, value in (
                    ("permission", requested),
                    ("source", fields.get("source", "")),
                    ("target", fields.get("target", "")),
                    ("class", fields.get("class", "")),
                )
                if value
            )
            results.append(
                self._point_event(
                    record,
                    kind=LogcatEventKind.SELINUX_DENIAL,
                    severity=LogcatEventSeverity.WARNING,
                    confidence=LogcatEventConfidence.EXACT,
                    title=f"SELinux denial{f': {requested}' if requested else ''}",
                    summary=useful or text,
                    detector_id="selinux-avc-denied-v1",
                    process=process,
                    fingerprint_parts=(
                        requested,
                        fields.get("source", ""),
                        fields.get("target", ""),
                        fields.get("class", ""),
                    ),
                )
            )
            return tuple(results)
        if "permission denial:" in folded:
            permission = _PERMISSION_NAME.search(text)
            results.append(
                self._point_event(
                    record,
                    kind=LogcatEventKind.PERMISSION_DENIAL,
                    severity=LogcatEventSeverity.ERROR,
                    confidence=LogcatEventConfidence.EXACT,
                    title="Android permission denial",
                    summary=text,
                    detector_id="android-permission-denial-v1",
                    fingerprint_parts=(permission.group(0) if permission else text,),
                )
            )
            return tuple(results)
        if (
            re.search(r"\brequires\b.+\bpermission\b", text, re.IGNORECASE)
            or (
                "operation not allowed" in folded
                and ("android.permission." in text or " permission" in folded)
            )
        ):
            permission = _PERMISSION_NAME.search(text)
            results.append(
                self._point_event(
                    record,
                    kind=LogcatEventKind.PERMISSION_DENIAL,
                    severity=LogcatEventSeverity.WARNING,
                    confidence=LogcatEventConfidence.STRONG,
                    title="Required Android permission missing",
                    summary=text,
                    detector_id="android-required-permission-v1",
                    fingerprint_parts=(permission.group(0) if permission else text,),
                )
            )
            return tuple(results)
        if "securityexception" in folded:
            exception = re.search(
                r"(?:java\.lang\.)?SecurityException(?::\s*(.*))?", text
            )
            detail = exception.group(1) if exception and exception.group(1) else text
            results.append(
                self._point_event(
                    record,
                    kind=LogcatEventKind.SECURITY_EXCEPTION,
                    severity=LogcatEventSeverity.ERROR,
                    confidence=LogcatEventConfidence.EXACT,
                    title="Android SecurityException",
                    summary=detail,
                    detector_id="android-security-exception-v1",
                    fingerprint_parts=(detail,),
                )
            )
            return tuple(results)
        death = _PROCESS_DIED.search(text) or _PROCESS_KILLING.search(text)
        if death:
            pid = int(death.group("pid"))
            if (
                pid not in self._recent_crash_pids
                or record.sequence - self._recent_crash_pids[pid] > 50
            ):
                process = death.group("process")
                results.append(
                    self._point_event(
                        record,
                        kind=LogcatEventKind.PROCESS_DEATH,
                        severity=LogcatEventSeverity.INFORMATION,
                        confidence=LogcatEventConfidence.EXACT,
                        title=f"Process ended: {process}",
                        summary=text,
                        detector_id="activity-manager-process-death-v1",
                        process=process,
                        pid=pid,
                        fingerprint_parts=("activity-manager-process-death",),
                    )
                )
        return tuple(results)

    def feed(self, record: LogcatRecord) -> tuple[DetectedLogcatEvent, ...]:
        emitted: list[DetectedLogcatEvent] = []
        candidate = self._candidate
        consumed = False
        if candidate is not None:
            if self._candidate_associated(candidate, record):
                self._append_candidate(candidate, record)
                consumed = True
                if self._candidate_ready(candidate):
                    emitted.append(self._candidate_draft(candidate, complete=False))
            else:
                emitted.append(self._candidate_draft(candidate, complete=True))
                if candidate.kind in {
                    LogcatEventKind.JAVA_CRASH,
                    LogcatEventKind.NATIVE_CRASH,
                } and candidate.pid is not None:
                    self._recent_crash_pids[candidate.pid] = candidate.records[-1].sequence
                self._candidate = None

        if not consumed:
            if self._is_java_start(record):
                self._candidate = _Candidate(
                    LogcatEventKind.JAVA_CRASH,
                    "android-runtime-fatal-exception-v1",
                    record,
                )
            elif self._is_native_start(record):
                signal = _NATIVE_SIGNAL.search(_message(record))
                candidate = _Candidate(
                    LogcatEventKind.NATIVE_CRASH,
                    "android-native-fatal-signal-v1",
                    record,
                )
                candidate.signal = signal.group("signal") if signal else ""
                if signal is None:
                    candidate.signal = "native-crash-dump"
                if signal:
                    candidate.pid = int(signal.group("pid"))
                    candidate.tid = (
                        int(signal.group("tid")) if signal.group("tid") else record.tid
                    )
                self._candidate = candidate
            elif self._is_anr_start(record):
                process = _ANR_PROCESS.search(_message(record))
                candidate = _Candidate(
                    LogcatEventKind.ANR,
                    "android-activity-manager-anr-v1",
                    record,
                )
                candidate.process = process.group("process") if process else ""
                reason = _ANR_REASON.search(_message(record))
                candidate.reason = reason.group("reason").strip() if reason else ""
                self._candidate = candidate
                emitted.append(self._candidate_draft(candidate, complete=False))
            else:
                emitted.extend(self._detect_point(record))
        return tuple(emitted)

    def flush(self) -> tuple[DetectedLogcatEvent, ...]:
        candidate, self._candidate = self._candidate, None
        if candidate is None:
            return ()
        if candidate.kind in {
            LogcatEventKind.JAVA_CRASH,
            LogcatEventKind.NATIVE_CRASH,
        } and candidate.pid is not None:
            self._recent_crash_pids[candidate.pid] = candidate.records[-1].sequence
        return (self._candidate_draft(candidate, complete=True),)
