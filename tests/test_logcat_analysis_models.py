import unittest
from dataclasses import FrozenInstanceError

from app.modules.logcat import (
    MAX_CONTEXT_RECORDS,
    MAX_EVENT_SUMMARY,
    MAX_EVENT_TITLE,
    MAX_STACK_LINE,
    MAX_STACK_LINES,
    LogcatAnalysisFilter,
    LogcatAnalysisService,
    LogcatCaptureSnapshot,
    LogcatEvent,
    LogcatEventConfidence,
    LogcatEventKind,
    LogcatEventSeverity,
    LogcatPriority,
    LogcatRecord,
)


def record(sequence, message, *, tag="ActivityManager"):
    return LogcatRecord(
        sequence,
        f"07-30 12:00:{sequence % 60:02d}.000",
        100,
        100,
        LogcatPriority.ERROR,
        tag,
        message,
        message,
        "parsed",
    )


class LogcatAnalysisModelTests(unittest.TestCase):
    def test_models_are_immutable_and_enforce_text_stack_context_bounds(self):
        source = tuple(record(index + 1, f"context {index}") for index in range(120))
        event = LogcatEvent(
            "event",
            "fingerprint",
            LogcatEventKind.JAVA_CRASH,
            LogcatEventSeverity.CRITICAL,
            LogcatEventConfidence.EXACT,
            "T" * (MAX_EVENT_TITLE + 50),
            "S" * (MAX_EVENT_SUMMARY + 50),
            stack_lines=tuple(
                "x" * (MAX_STACK_LINE + 20) for _ in range(MAX_STACK_LINES + 20)
            ),
            context_records=source,
            context_first_sequence=1,
            context_last_sequence=120,
        )
        self.assertEqual(len(event.title), MAX_EVENT_TITLE)
        self.assertEqual(len(event.summary), MAX_EVENT_SUMMARY)
        self.assertEqual(len(event.stack_lines), MAX_STACK_LINES)
        self.assertEqual(len(event.stack_lines[0]), MAX_STACK_LINE)
        self.assertEqual(len(event.context_records), MAX_CONTEXT_RECORDS)
        with self.assertRaises(FrozenInstanceError):
            event.title = "changed"
        with self.assertRaises(FrozenInstanceError):
            LogcatAnalysisFilter().text_search = "changed"

    def test_filter_kind_severity_process_and_text_are_local(self):
        event = LogcatEvent(
            "event",
            "fingerprint",
            LogcatEventKind.PERMISSION_DENIAL,
            LogcatEventSeverity.WARNING,
            LogcatEventConfidence.STRONG,
            "Camera permission denied",
            "android.permission.CAMERA",
            process="com.example.camera",
            detector_id="permission-v1",
        )
        self.assertTrue(
            LogcatAnalysisFilter(
                LogcatEventKind.PERMISSION_DENIAL,
                LogcatEventSeverity.WARNING,
                "example",
                "camera",
            ).matches(event)
        )
        self.assertFalse(
            LogcatAnalysisFilter(
                minimum_severity=LogcatEventSeverity.ERROR
            ).matches(event)
        )
        self.assertFalse(
            LogcatAnalysisFilter(kind=LogcatEventKind.ANR).matches(event)
        )

    def test_capacity_discards_oldest_and_clear_resets_every_counter(self):
        service = LogcatAnalysisService(capacity=2)
        records = tuple(
            record(
                index,
                f"Permission Denial: requires android.permission.FIXTURE_{index}",
            )
            for index in range(1, 4)
        )
        source = tuple(records)
        snapshot = service.consume_capture_snapshot(
            LogcatCaptureSnapshot(records=records)
        )
        self.assertEqual(snapshot.unique_event_count, 2)
        self.assertEqual(snapshot.dropped_event_groups, 1)
        self.assertEqual(snapshot.events[0].first_sequence, 2)
        self.assertEqual(records, source)
        cleared = service.clear()
        self.assertEqual(
            (
                cleared.unique_event_count,
                cleared.total_occurrence_count,
                cleared.dropped_event_groups,
                cleared.processed_record_count,
            ),
            (0, 0, 0, 0),
        )


if __name__ == "__main__":
    unittest.main()
