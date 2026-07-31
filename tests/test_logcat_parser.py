import unittest

from app.modules.logcat import MAX_RAW_LINE, LogcatPriority, ThreadtimeParser


class ThreadtimeParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = ThreadtimeParser()
        self.line = "07-30 12:34:56.789  123  456 I Demo Tag: hello: world"

    def test_valid_line_tag_spacing_and_message_colons(self):
        record = self.parser.parse(self.line, 1)
        self.assertEqual(record.device_timestamp, "07-30 12:34:56.789")
        self.assertEqual((record.pid, record.tid), (123, 456))
        self.assertEqual(record.priority, LogcatPriority.INFO)
        self.assertEqual(record.tag, "Demo Tag")
        self.assertEqual(record.message, "hello: world")
        self.assertEqual(record.parse_status, "parsed")

    def test_every_android_priority(self):
        for sequence, priority in enumerate(LogcatPriority, 1):
            with self.subTest(priority=priority):
                record = self.parser.parse(
                    self.line.replace(" I Demo", f" {priority.value} Demo"),
                    sequence,
                )
                self.assertEqual(record.priority, priority)

    def test_continuation_and_stack_like_lines_retain_relationship(self):
        first = self.parser.parse(self.line, 1)
        continuation = self.parser.parse("    at demo.Main.run(Main.java:9)", 2, first)
        self.assertEqual(continuation.parse_status, "continuation")
        self.assertEqual(continuation.continuation_of, 1)
        self.assertEqual((continuation.pid, continuation.tag), (123, "Demo Tag"))

    def test_malformed_and_blank_lines_become_bounded_records(self):
        malformed = self.parser.parse("not threadtime", 1)
        blank = self.parser.parse("\r\n", 2)
        self.assertEqual(malformed.parse_status, "malformed")
        self.assertEqual(malformed.raw_line, "not threadtime")
        self.assertEqual(blank.parse_status, "blank")

    def test_unicode_replacement_is_deterministic(self):
        record = self.parser.parse(
            b"07-30 12:34:56.789 1 2 I Tag: bad \xff bytes\n", 1
        )
        self.assertIn("\N{REPLACEMENT CHARACTER}", record.message)

    def test_oversized_lines_are_truncated(self):
        record = self.parser.parse("x" * (MAX_RAW_LINE + 200), 1)
        self.assertEqual(len(record.raw_line), MAX_RAW_LINE)
        self.assertEqual(record.parse_status, "malformed-truncated")

    def test_ansi_and_control_sequences_cannot_reach_the_gui(self):
        record = self.parser.parse(
            "07-30 12:34:56.789 1 2 W Tag: \x1b[31mred\x1b[0m\x00", 1
        )
        self.assertNotIn("\x1b", record.raw_line)
        self.assertNotIn("\x00", record.raw_line)
        self.assertEqual(record.message, "red\N{REPLACEMENT CHARACTER}")


if __name__ == "__main__":
    unittest.main()
