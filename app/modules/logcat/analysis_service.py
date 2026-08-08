"""Bounded incremental Logcat event grouping and local filtering."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import replace

from app.modules.logcat.analysis_models import (
    DEFAULT_CONTEXT_AFTER,
    DEFAULT_CONTEXT_BEFORE,
    MAX_CONTEXT_RECORDS,
    MAX_OCCURRENCE_SUMMARIES,
    MAX_UNIQUE_EVENTS,
    LogcatAnalysisFilter,
    LogcatAnalysisSnapshot,
    LogcatEvent,
    LogcatEventOccurrence,
)
from app.modules.logcat.detectors import DetectedLogcatEvent, LogcatDetectorEngine
from app.modules.logcat.models import LogcatCaptureSnapshot, LogcatRecord


class LogcatAnalysisService:
    """Consume capture snapshots once by sequence without owning capture or Tk."""

    def __init__(
        self,
        *,
        capacity: int = MAX_UNIQUE_EVENTS,
        context_before: int = DEFAULT_CONTEXT_BEFORE,
        context_after: int = DEFAULT_CONTEXT_AFTER,
        detector: LogcatDetectorEngine | None = None,
    ) -> None:
        if not 1 <= int(capacity) <= MAX_UNIQUE_EVENTS:
            raise ValueError(
                f"Analysis capacity must be between 1 and {MAX_UNIQUE_EVENTS}."
            )
        if not 0 <= int(context_before) <= MAX_CONTEXT_RECORDS:
            raise ValueError("Context-before bound is invalid.")
        if not 0 <= int(context_after) <= MAX_CONTEXT_RECORDS:
            raise ValueError("Context-after bound is invalid.")
        if int(context_before) + int(context_after) + 1 > MAX_CONTEXT_RECORDS:
            raise ValueError("Combined event context exceeds its supported bound.")
        self.capacity = int(capacity)
        self.context_before = int(context_before)
        self.context_after = int(context_after)
        self.detector = detector or LogcatDetectorEngine()
        self._events: OrderedDict[str, LogcatEvent] = OrderedDict()
        self._occurrence_to_fingerprint: dict[str, str] = {}
        self._open_context_deadlines: dict[str, int] = {}
        self._filter = LogcatAnalysisFilter()
        self._filter_generation = 0
        self._dropped = 0
        self._last_sequence = 0
        self._processed = 0
        self._latency_ms = 0.0
        self._closed = False
        self._lock = threading.RLock()

    def snapshot(self) -> LogcatAnalysisSnapshot:
        with self._lock:
            events = tuple(self._events.values())
            current_filter = self._filter
            values = (
                self._dropped,
                self._filter_generation,
                self._last_sequence,
                self._processed,
                self._latency_ms,
            )
        visible = tuple(event for event in events if current_filter.matches(event))
        return LogcatAnalysisSnapshot(
            events,
            visible,
            values[0],
            current_filter,
            values[1],
            values[2],
            values[3],
            values[4],
        )

    def set_filter(self, value: LogcatAnalysisFilter) -> LogcatAnalysisSnapshot:
        if not isinstance(value, LogcatAnalysisFilter):
            raise TypeError("Analysis filter must be an immutable LogcatAnalysisFilter.")
        with self._lock:
            if self._closed:
                return self.snapshot()
            self._filter = value
            self._filter_generation += 1
        return self.snapshot()

    def reset_filters(self) -> LogcatAnalysisSnapshot:
        return self.set_filter(LogcatAnalysisFilter())

    @staticmethod
    def _occurrence(draft: DetectedLogcatEvent) -> LogcatEventOccurrence:
        return LogcatEventOccurrence(
            draft.first_sequence,
            draft.last_sequence,
            draft.first_timestamp_text,
            draft.last_timestamp_text,
            draft.summary,
            draft.relevant_record_sequences,
        )

    def _context_for(
        self,
        draft: DetectedLogcatEvent,
        source_records: tuple[LogcatRecord, ...],
    ) -> tuple[LogcatRecord, ...]:
        first = max(1, draft.first_sequence - self.context_before)
        last = draft.last_sequence + self.context_after
        if not source_records:
            return ()
        source_first = source_records[0].sequence
        start_index = max(0, first - source_first)
        stop_index = min(len(source_records), last - source_first + 1)
        values = tuple(
            record
            for record in source_records[start_index:stop_index]
            if first <= record.sequence <= last
        )
        return values[-MAX_CONTEXT_RECORDS:]

    @staticmethod
    def _replace_occurrence(
        values: tuple[LogcatEventOccurrence, ...],
        incoming: LogcatEventOccurrence,
    ) -> tuple[LogcatEventOccurrence, ...]:
        replaced = False
        result = []
        for value in values:
            if value.first_sequence == incoming.first_sequence:
                result.append(incoming)
                replaced = True
            else:
                result.append(value)
        if not replaced:
            result.append(incoming)
        return tuple(result[-MAX_OCCURRENCE_SUMMARIES:])

    def _remove_event_references(self, fingerprint: str) -> None:
        for key, value in tuple(self._occurrence_to_fingerprint.items()):
            if value == fingerprint:
                self._occurrence_to_fingerprint.pop(key, None)
                self._open_context_deadlines.pop(key, None)

    def _upsert(
        self,
        draft: DetectedLogcatEvent,
        source_records: tuple[LogcatRecord, ...],
    ) -> None:
        occurrence = self._occurrence(draft)
        context = self._context_for(draft, source_records)
        existing_fingerprint = self._occurrence_to_fingerprint.get(
            draft.occurrence_key
        )
        if existing_fingerprint and existing_fingerprint != draft.fingerprint:
            self._occurrence_to_fingerprint.pop(draft.occurrence_key, None)
            existing_fingerprint = None
        event = self._events.get(draft.fingerprint)
        same_occurrence = existing_fingerprint == draft.fingerprint
        if event is None:
            event = LogcatEvent(
                event_id=f"logcat-{draft.fingerprint[:24]}",
                fingerprint=draft.fingerprint,
                kind=draft.kind,
                severity=draft.severity,
                confidence=draft.confidence,
                title=draft.title,
                summary=draft.summary,
                process=draft.process,
                package=draft.package,
                pid=draft.pid,
                tid=draft.tid,
                first_sequence=draft.first_sequence,
                last_sequence=draft.last_sequence,
                first_timestamp_text=draft.first_timestamp_text,
                last_timestamp_text=draft.last_timestamp_text,
                occurrence_count=1,
                context_first_sequence=(
                    context[0].sequence if context else draft.first_sequence
                ),
                context_last_sequence=(
                    context[-1].sequence if context else draft.last_sequence
                ),
                relevant_record_sequences=draft.relevant_record_sequences,
                stack_lines=draft.stack_lines,
                detector_id=draft.detector_id,
                occurrences=(occurrence,),
                context_records=context,
            )
            self._events[draft.fingerprint] = event
            if len(self._events) > self.capacity:
                removed_fingerprint, _removed = self._events.popitem(last=False)
                self._remove_event_references(removed_fingerprint)
                self._dropped += 1
        else:
            occurrences = self._replace_occurrence(event.occurrences, occurrence)
            event = replace(
                event,
                severity=(
                    draft.severity
                    if draft.severity.rank > event.severity.rank
                    else event.severity
                ),
                confidence=draft.confidence,
                title=draft.title,
                summary=draft.summary,
                process=draft.process or event.process,
                package=draft.package or event.package,
                pid=draft.pid if draft.pid is not None else event.pid,
                tid=draft.tid if draft.tid is not None else event.tid,
                last_sequence=max(event.last_sequence, draft.last_sequence),
                last_timestamp_text=(
                    draft.last_timestamp_text or event.last_timestamp_text
                ),
                occurrence_count=(
                    event.occurrence_count
                    if same_occurrence
                    else event.occurrence_count + 1
                ),
                context_first_sequence=(
                    context[0].sequence if context else draft.first_sequence
                ),
                context_last_sequence=(
                    context[-1].sequence if context else draft.last_sequence
                ),
                relevant_record_sequences=draft.relevant_record_sequences,
                stack_lines=draft.stack_lines,
                detector_id=draft.detector_id,
                occurrences=occurrences,
                context_records=context,
            )
            self._events[draft.fingerprint] = event
        self._occurrence_to_fingerprint[draft.occurrence_key] = draft.fingerprint
        self._open_context_deadlines[draft.occurrence_key] = (
            draft.last_sequence + self.context_after
        )

    def _extend_open_context(self, record: LogcatRecord) -> None:
        for occurrence_key, deadline in tuple(self._open_context_deadlines.items()):
            fingerprint = self._occurrence_to_fingerprint.get(occurrence_key)
            event = self._events.get(fingerprint or "")
            if event is None:
                self._open_context_deadlines.pop(occurrence_key, None)
                continue
            if record.sequence > deadline:
                self._open_context_deadlines.pop(occurrence_key, None)
                continue
            if record.sequence <= event.context_last_sequence:
                continue
            context = (*event.context_records, record)[-MAX_CONTEXT_RECORDS:]
            self._events[fingerprint] = replace(
                event,
                context_first_sequence=context[0].sequence,
                context_last_sequence=context[-1].sequence,
                context_records=context,
            )

    def consume_capture_snapshot(
        self, capture: LogcatCaptureSnapshot
    ) -> LogcatAnalysisSnapshot:
        started = time.perf_counter()
        with self._lock:
            if self._closed:
                return self.snapshot()
            source_records = tuple(capture.records)
            if not source_records or source_records[-1].sequence <= self._last_sequence:
                new_records = ()
            else:
                first_sequence = source_records[0].sequence
                start_index = max(0, self._last_sequence - first_sequence + 1)
                new_records = source_records[start_index:]
            for record in new_records:
                self._extend_open_context(record)
                for draft in self.detector.feed(record):
                    self._upsert(draft, source_records)
                self._last_sequence = record.sequence
                self._processed += 1
            self._latency_ms = (time.perf_counter() - started) * 1_000
        return self.snapshot()

    def flush(self, source_records: tuple[LogcatRecord, ...] = ()) -> None:
        with self._lock:
            if self._closed:
                return
            for draft in self.detector.flush():
                self._upsert(draft, tuple(source_records))

    def clear(self) -> LogcatAnalysisSnapshot:
        with self._lock:
            self.detector.reset()
            self._events.clear()
            self._occurrence_to_fingerprint.clear()
            self._open_context_deadlines.clear()
            self._dropped = 0
            self._last_sequence = 0
            self._processed = 0
            self._latency_ms = 0.0
        return self.snapshot()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self.clear()
            self._closed = True

    cleanup = close

    @property
    def worker_count(self) -> int:
        return 0

    @property
    def callback_count(self) -> int:
        return 0
