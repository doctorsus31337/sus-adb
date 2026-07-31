import unittest
from dataclasses import FrozenInstanceError

from app.modules.logcat import (
    DEFAULT_CAPACITY,
    MAX_CAPACITY,
    MIN_CAPACITY,
    LogcatCaptureService,
    LogcatFilter,
    LogcatPriority,
    LogcatRecord,
)


class LogcatModelTests(unittest.TestCase):
    def record(self, sequence=1, **values):
        return LogcatRecord(
            sequence,
            "07-30 12:00:00.000",
            123,
            456,
            LogcatPriority.INFO,
            "Demo",
            "Hello World",
            "07-30 12:00:00.000 123 456 I Demo: Hello World",
            "parsed",
            **values,
        )

    def test_records_filters_and_priorities_are_immutable(self):
        record = self.record()
        with self.assertRaises(FrozenInstanceError):
            record.message = "changed"
        self.assertEqual(
            tuple(priority.label for priority in LogcatPriority),
            ("Verbose", "Debug", "Info", "Warn", "Error", "Fatal"),
        )
        self.assertTrue(
            LogcatFilter(
                LogcatPriority.INFO, "em", 123, "hello"
            ).matches(record)
        )
        self.assertFalse(LogcatFilter(LogcatPriority.WARN).matches(record))

    def test_filtering_does_not_mutate_source_records(self):
        records = (self.record(), self.record(2))
        source = tuple(records)
        visible = tuple(
            record
            for record in records
            if LogcatFilter(message_substring="world").matches(record)
        )
        self.assertEqual(visible, records)
        self.assertEqual(records, source)

    def test_capacity_defaults_and_supported_bounds(self):
        self.assertEqual(DEFAULT_CAPACITY, 10_000)
        self.assertEqual((MIN_CAPACITY, MAX_CAPACITY), (1_000, 50_000))
        with self.assertRaises(ValueError):
            LogcatCaptureService("adb", capacity=999)
        with self.assertRaises(ValueError):
            LogcatCaptureService("adb", capacity=50_001)


if __name__ == "__main__":
    unittest.main()
