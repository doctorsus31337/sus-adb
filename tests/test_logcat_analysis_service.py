import unittest

from app.modules.logcat import (
    LogcatAnalysisFilter,
    LogcatAnalysisService,
    LogcatCaptureSnapshot,
    LogcatCaptureState,
    LogcatEventKind,
    LogcatEventSeverity,
    LogcatPriority,
    LogcatRecord,
)


def denial(sequence, permission="CAMERA"):
    text = f"Permission Denial: requires android.permission.{permission}"
    return LogcatRecord(
        sequence,
        f"07-30 12:00:{sequence % 60:02d}.000",
        100,
        100,
        LogcatPriority.ERROR,
        "ActivityManager",
        text,
        text,
        "parsed",
    )


class LogcatAnalysisServiceTests(unittest.TestCase):
    def test_new_sequences_once_duplicate_snapshots_rollover_and_context(self):
        service = LogcatAnalysisService()
        first = tuple(denial(index) for index in range(1, 6))
        service.consume_capture_snapshot(LogcatCaptureSnapshot(records=first))
        original = service.snapshot()
        self.assertEqual(original.processed_record_count, 5)
        self.assertEqual(original.total_occurrence_count, 5)
        service.consume_capture_snapshot(LogcatCaptureSnapshot(records=first))
        duplicate = service.snapshot()
        self.assertEqual(duplicate.processed_record_count, 5)
        self.assertEqual(duplicate.total_occurrence_count, 5)
        rolled = (*first[-2:], denial(6), denial(7))
        service.consume_capture_snapshot(LogcatCaptureSnapshot(records=rolled))
        current = service.snapshot()
        self.assertEqual(current.processed_record_count, 7)
        self.assertEqual(current.total_occurrence_count, 7)
        self.assertLessEqual(len(current.events[0].context_records), 100)

    def test_grouping_stable_id_occurrences_and_process_separation(self):
        service = LogcatAnalysisService()
        records = (
            denial(1),
            denial(2),
            LogcatRecord(
                3,
                "07-30 12:00:03.000",
                200,
                200,
                LogcatPriority.ERROR,
                "Other",
                "Permission Denial: requires android.permission.CAMERA",
                "Permission Denial: requires android.permission.CAMERA",
                "parsed",
            ),
        )
        service.consume_capture_snapshot(LogcatCaptureSnapshot(records=records))
        events = service.snapshot().events
        self.assertEqual(len(events), 2)
        grouped = next(value for value in events if value.pid == 100)
        self.assertEqual(grouped.occurrence_count, 2)
        self.assertEqual(grouped.event_id, f"logcat-{grouped.fingerprint[:24]}")

    def test_filters_counts_and_reset_do_not_mutate_events(self):
        service = LogcatAnalysisService()
        records = (
            denial(1),
            LogcatRecord(
                2,
                "07-30 12:00:02.000",
                200,
                200,
                LogcatPriority.ERROR,
                "Binder",
                "java.lang.SecurityException: rejected",
                "java.lang.SecurityException: rejected",
                "parsed",
            ),
        )
        service.consume_capture_snapshot(LogcatCaptureSnapshot(records=records))
        source = service.snapshot().events
        filtered = service.set_filter(
            LogcatAnalysisFilter(
                kind=LogcatEventKind.PERMISSION_DENIAL,
                minimum_severity=LogcatEventSeverity.WARNING,
                text_search="camera",
            )
        )
        self.assertEqual(filtered.unique_event_count, 2)
        self.assertEqual(filtered.visible_event_count, 1)
        self.assertEqual(filtered.total_occurrence_count, 2)
        self.assertEqual(service.snapshot().events, source)
        reset = service.reset_filters()
        self.assertEqual(reset.visible_event_count, 2)

    def test_pause_state_does_not_pause_analysis_and_resume_does_not_duplicate(self):
        service = LogcatAnalysisService()
        first = LogcatCaptureSnapshot(
            state=LogcatCaptureState.VIEW_PAUSED,
            records=(denial(1), denial(2)),
        )
        service.consume_capture_snapshot(first)
        self.assertEqual(service.snapshot().total_occurrence_count, 2)
        service.consume_capture_snapshot(
            LogcatCaptureSnapshot(
                state=LogcatCaptureState.RUNNING,
                records=first.records,
            )
        )
        self.assertEqual(service.snapshot().total_occurrence_count, 2)

    def test_clear_close_have_no_worker_callback_or_residual_state(self):
        service = LogcatAnalysisService()
        service.consume_capture_snapshot(
            LogcatCaptureSnapshot(records=(denial(1),))
        )
        self.assertEqual(service.clear().unique_event_count, 0)
        service.close()
        self.assertEqual(service.snapshot().unique_event_count, 0)
        self.assertEqual((service.worker_count, service.callback_count), (0, 0))

    def test_ten_thousand_records_are_incremental_and_bounded(self):
        service = LogcatAnalysisService()
        records = tuple(
            LogcatRecord(
                index,
                "",
                100,
                100,
                LogcatPriority.INFO,
                "Demo",
                f"ordinary message {index}",
                f"ordinary message {index}",
                "parsed",
            )
            for index in range(1, 10_001)
        )
        result = service.consume_capture_snapshot(
            LogcatCaptureSnapshot(records=records)
        )
        self.assertEqual(result.processed_record_count, 10_000)
        self.assertEqual(result.unique_event_count, 0)
        self.assertLess(result.analysis_latency_ms, 2_000)


if __name__ == "__main__":
    unittest.main()
