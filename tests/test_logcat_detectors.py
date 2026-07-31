import unittest

from app.modules.logcat import (
    LogcatAnalysisService,
    LogcatCaptureSnapshot,
    LogcatEventKind,
    LogcatEventSeverity,
    ThreadtimeParser,
    normalize_fingerprint_text,
)


class LogcatDetectorTests(unittest.TestCase):
    def analyze(self, lines):
        parser = ThreadtimeParser()
        records = []
        previous = None
        for sequence, line in enumerate(lines, 1):
            current = parser.parse(line, sequence, previous)
            records.append(current)
            previous = current
        service = LogcatAnalysisService()
        snapshot = service.consume_capture_snapshot(
            LogcatCaptureSnapshot(records=tuple(records))
        )
        service.flush(tuple(records))
        return service.snapshot(), tuple(records)

    def test_java_fatal_process_exception_stack_caused_by_and_grouping(self):
        crash = (
            "07-30 12:00:00.000 123 123 E AndroidRuntime: FATAL EXCEPTION: main",
            "07-30 12:00:00.001 123 123 E AndroidRuntime: Process: com.demo, PID: 123",
            "07-30 12:00:00.002 123 123 E AndroidRuntime: java.lang.IllegalStateException: bad",
            "07-30 12:00:00.003 123 123 E AndroidRuntime:     at com.demo.Main.run(Main.java:42)",
            "07-30 12:00:00.004 123 123 E AndroidRuntime: Caused by: java.lang.RuntimeException: nested",
            "07-30 12:00:00.005 100 100 I Demo: boundary",
        )
        repeated = tuple(
            value.replace(" 123 123 ", " 999 999 ")
            .replace("PID: 123", "PID: 999")
            .replace("Main.java:42", "Main.java:901")
            for value in crash
        )
        snapshot, _records = self.analyze((*crash, *repeated))
        event = next(value for value in snapshot.events if value.kind is LogcatEventKind.JAVA_CRASH)
        self.assertEqual(event.process, "com.demo")
        self.assertEqual(event.occurrence_count, 2)
        self.assertIn("IllegalStateException", event.title)
        self.assertTrue(any("at com.demo.Main.run" in line for line in event.stack_lines))
        self.assertTrue(any("Caused by:" in line for line in event.stack_lines))
        self.assertEqual(len(event.occurrences), 2)

    def test_unrelated_stack_looking_text_is_not_a_java_crash(self):
        snapshot, _records = self.analyze(
            (
                "07-30 12:00:00.000 123 123 I Demo: at com.demo.Main.run(Main.java:42)",
                "    at com.demo.Other.run(Other.java:8)",
            )
        )
        self.assertFalse(snapshot.events)

    def test_native_signal_abort_backtrace_address_normalization_and_grouping(self):
        crash = (
            "07-30 12:00:00.000 123 124 F libc: Fatal signal 11 (SIGSEGV), code 1, fault addr 0x12345678 in tid 124, pid 123",
            "07-30 12:00:00.001 123 124 F DEBUG: pid: 123, tid: 124, name: worker  >>> com.demo.native <<<",
            "07-30 12:00:00.002 123 124 F DEBUG: Abort message: 'fixture abort'",
            "07-30 12:00:00.003 123 124 F DEBUG: backtrace:",
            "07-30 12:00:00.004 123 124 F DEBUG:     #00 pc 000000001234abcd /data/app/libdemo.so (demo_crash+0x44)",
            "07-30 12:00:00.005 100 100 I Demo: boundary",
        )
        repeated = tuple(
            value.replace("000000001234abcd", "00000000deadbeef")
            .replace("+0x44", "+0x99")
            for value in crash
        )
        snapshot, _records = self.analyze((*crash, *repeated))
        event = next(value for value in snapshot.events if value.kind is LogcatEventKind.NATIVE_CRASH)
        self.assertEqual(event.process, "com.demo.native")
        self.assertEqual(event.occurrence_count, 2)
        self.assertIn("SIGSEGV", event.title)
        self.assertIn("fixture abort", event.summary)
        self.assertEqual(len(event.stack_lines), 1)
        self.assertEqual(
            normalize_fingerprint_text("pc 000000001234abcd foo+0x44"),
            normalize_fingerprint_text("pc 00000000deadbeef foo+0x99"),
        )

    def test_unrelated_libc_warning_is_not_native_crash(self):
        snapshot, _records = self.analyze(
            ("07-30 12:00:00.000 123 124 W libc: allocator warning",)
        )
        self.assertFalse(snapshot.events)

    def test_anr_in_input_timeout_reason_and_slow_warning_boundary(self):
        snapshot, _records = self.analyze(
            (
                "07-30 12:00:00.000 100 100 E ActivityManager: ANR in com.demo",
                "07-30 12:00:00.001 100 100 E ActivityManager: Reason: Input dispatching timed out",
                "07-30 12:00:00.002 100 100 I Demo: boundary",
                "07-30 12:00:00.003 100 100 W Demo: slow operation took 9000ms",
                "07-30 12:00:00.004 100 100 E InputDispatcher: Input dispatching timed out for com.other",
                "07-30 12:00:00.005 100 100 I Demo: boundary",
            )
        )
        anrs = tuple(value for value in snapshot.events if value.kind is LogcatEventKind.ANR)
        self.assertEqual(len(anrs), 2)
        self.assertTrue(any("Input dispatching timed out" in value.summary for value in anrs))
        self.assertFalse(any("slow operation" in value.summary for value in anrs))

    def test_security_permission_required_and_selinux_are_distinct(self):
        snapshot, _records = self.analyze(
            (
                "07-30 12:00:00.000 200 200 E Binder: java.lang.SecurityException: caller rejected",
                "07-30 12:00:00.001 201 201 W ActivityManager: Permission Denial: opening provider requires android.permission.CAMERA",
                "07-30 12:00:00.002 202 202 W PackageManager: operation requires android.permission.READ_CONTACTS permission",
                '07-30 12:00:00.003 203 203 W auditd: avc: denied { read } for comm=\"demo\" scontext=u:r:untrusted_app:s0 tcontext=u:object_r:secret:s0 tclass=file',
                "07-30 12:00:00.004 204 204 I PackageManager: permission android.permission.INTERNET granted",
            )
        )
        kinds = tuple(value.kind for value in snapshot.events)
        self.assertEqual(kinds.count(LogcatEventKind.SECURITY_EXCEPTION), 1)
        self.assertEqual(kinds.count(LogcatEventKind.PERMISSION_DENIAL), 2)
        self.assertEqual(kinds.count(LogcatEventKind.SELINUX_DENIAL), 1)
        selinux = next(
            value for value in snapshot.events
            if value.kind is LogcatEventKind.SELINUX_DENIAL
        )
        self.assertIn("source=u:r:untrusted_app:s0", selinux.summary)
        self.assertIn("class=file", selinux.summary)
        self.assertEqual(selinux.process, "demo")

    def test_process_death_is_informational_and_crash_precedes_death(self):
        standalone, _records = self.analyze(
            (
                "07-30 12:00:00.000 100 100 I ActivityManager: Process com.demo (pid 321) has died",
            )
        )
        death = standalone.events[0]
        self.assertEqual(death.kind, LogcatEventKind.PROCESS_DEATH)
        self.assertEqual(death.severity, LogcatEventSeverity.INFORMATION)
        crash, _records = self.analyze(
            (
                "07-30 12:00:00.000 321 321 E AndroidRuntime: FATAL EXCEPTION: main",
                "07-30 12:00:00.001 321 321 E AndroidRuntime: Process: com.demo, PID: 321",
                "07-30 12:00:00.002 321 321 E AndroidRuntime: java.lang.RuntimeException: bad",
                "07-30 12:00:00.003 321 321 E AndroidRuntime:     at com.demo.Main.run(Main.java:1)",
                "07-30 12:00:00.004 100 100 I ActivityManager: Process com.demo (pid 321) has died",
            )
        )
        self.assertEqual(
            tuple(value.kind for value in crash.events),
            (LogcatEventKind.JAVA_CRASH,),
        )


if __name__ == "__main__":
    unittest.main()
