import queue
import subprocess
import threading
import time
import unittest

from app.modules.logcat import (
    LogcatCaptureService,
    LogcatCaptureState,
    LogcatFilter,
    LogcatPriority,
)


class FakeStream:
    EOF = object()

    def __init__(self):
        self.values = queue.Queue()
        self.closed = False

    def feed(self, value):
        self.values.put(value)

    def fail(self, error):
        self.values.put(error)

    def readline(self):
        value = self.values.get(timeout=2)
        if value is self.EOF:
            return b""
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        if not self.closed:
            self.closed = True
            self.values.put(self.EOF)


class FakeProcess:
    def __init__(self):
        self.stdout = FakeStream()
        self.stderr = FakeStream()
        self.returncode = None
        self.terminated = 0
        self.killed = 0
        self.finished = threading.Event()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if not self.finished.wait(timeout):
            raise subprocess.TimeoutExpired("fake", timeout)
        return self.returncode

    def terminate(self):
        self.terminated += 1
        self.exit(0)

    def kill(self):
        self.killed += 1
        self.exit(-9)

    def exit(self, returncode):
        if self.returncode is None:
            self.returncode = returncode
            self.stdout.close()
            self.stderr.close()
            self.finished.set()


class Factory:
    def __init__(self):
        self.calls = []
        self.processes = []

    def __call__(self, argv, **kwargs):
        process = FakeProcess()
        self.calls.append((tuple(argv), kwargs))
        self.processes.append(process)
        return process


def wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


class LogcatCaptureServiceTests(unittest.TestCase):
    LINE = b"07-30 12:34:56.789  123  456 I Demo: hello world\n"

    def service(self, capacity=1_000):
        factory = Factory()
        service = LogcatCaptureService(
            "/tools with spaces/adb",
            process_factory=factory,
            capacity=capacity,
            batch_interval=0.02,
            stop_timeout=0.1,
        )
        self.addCleanup(service.close)
        return service, factory

    def test_constructor_and_missing_serial_start_nothing(self):
        service, factory = self.service()
        self.assertEqual(service.snapshot().state, LogcatCaptureState.IDLE)
        self.assertFalse(service.start("").ok)
        self.assertEqual(factory.calls, [])
        self.assertEqual(service.worker_count, 0)

    def test_start_binds_exact_serial_and_structured_shell_false_argv(self):
        service, factory = self.service()
        self.assertTrue(service.start(" USB SERIAL ").ok)
        argv, kwargs = factory.calls[0]
        self.assertEqual(
            argv,
            (
                "/tools with spaces/adb",
                "-s",
                "USB SERIAL",
                "logcat",
                "-v",
                "threadtime",
            ),
        )
        self.assertIs(kwargs["shell"], False)
        self.assertIs(kwargs["text"], False)
        self.assertFalse(service.start("OTHER").ok)
        self.assertEqual(len(factory.calls), 1)

    def test_stdout_stderr_pause_resume_and_device_change(self):
        service, factory = self.service()
        seen = []
        subscription = service.subscribe(seen.append)
        self.addCleanup(subscription.cancel)
        service.start("SERIAL")
        process = factory.processes[0]
        process.stdout.feed(self.LINE)
        process.stderr.feed(b"bounded diagnostic\n")
        self.assertTrue(wait_for(lambda: service.snapshot().buffered_count == 1))
        service.pause_view()
        self.assertEqual(service.snapshot().state, LogcatCaptureState.VIEW_PAUSED)
        process.stdout.feed(self.LINE.replace(b"hello", b"second"))
        self.assertTrue(wait_for(lambda: service.snapshot().buffered_count == 2))
        service.set_selected_serial("OTHER")
        snapshot = service.snapshot()
        self.assertEqual(snapshot.capture_serial, "SERIAL")
        self.assertEqual(snapshot.selected_serial, "OTHER")
        self.assertEqual(service.argv[2], "SERIAL")
        self.assertTrue(service.resume_view().ok)
        self.assertTrue(wait_for(lambda: bool(seen)))

    def test_capacity_discards_oldest_counts_drops_filters_and_clear(self):
        service, factory = self.service()
        service.start("SERIAL")
        process = factory.processes[0]
        for index in range(1_001):
            process.stdout.feed(
                self.LINE.replace(b"hello world", f"message {index}".encode())
            )
        self.assertTrue(wait_for(lambda: service.snapshot().dropped_records == 1))
        snapshot = service.snapshot()
        self.assertEqual(snapshot.buffered_count, 1_000)
        self.assertEqual(snapshot.records[0].message, "message 1")
        service.set_filter(
            LogcatFilter(
                LogcatPriority.INFO,
                tag_substring="demo",
                pid=123,
                message_substring="message 1000",
            )
        )
        self.assertEqual(service.snapshot().visible_count, 1)
        source = service.snapshot().records
        service.set_filter(LogcatFilter(LogcatPriority.ERROR))
        self.assertEqual(service.snapshot().records, source)
        cleared = service.clear()
        self.assertEqual((cleared.buffered_count, cleared.dropped_records), (0, 0))
        self.assertIn("Android Logcat was not cleared", cleared.status_text)
        self.assertEqual(len(factory.calls), 1)

    def test_stop_is_owned_idempotent_and_close_clears_every_resource(self):
        service, factory = self.service()
        subscription = service.subscribe(lambda _snapshot: None)
        service.start("SERIAL")
        process = factory.processes[0]
        self.assertTrue(service.stop().ok)
        self.assertEqual(process.terminated, 1)
        self.assertTrue(service.stop().ok)
        self.assertEqual(process.terminated, 1)
        service.close()
        subscription.cancel()
        self.assertEqual(service.snapshot().state, LogcatCaptureState.CLOSED)
        self.assertEqual(service.snapshot().buffered_count, 0)
        self.assertEqual(service.worker_count, 0)
        self.assertEqual(service.callback_count, 0)
        self.assertEqual(service.process_count, 0)

    def test_unexpected_exit_and_reader_error_are_structured(self):
        service, factory = self.service()
        service.start("SERIAL")
        factory.processes[0].exit(7)
        self.assertTrue(
            wait_for(lambda: service.snapshot().state is LogcatCaptureState.FAILED)
        )
        self.assertIn("code 7", service.snapshot().error_text)
        service.stop()
        self.assertTrue(service.start("SERIAL").ok)
        factory.processes[1].stdout.fail(OSError("reader fixture"))
        self.assertTrue(
            wait_for(lambda: service.snapshot().state is LogcatCaptureState.FAILED)
        )
        self.assertIn("reader failed", service.snapshot().error_text)

    def test_dispatch_is_batched_instead_of_one_callback_per_record(self):
        service, factory = self.service()
        delivered = []
        service.subscribe(delivered.append, replay=False)
        service.start("SERIAL")
        process = factory.processes[0]
        for _ in range(100):
            process.stdout.feed(self.LINE)
        self.assertTrue(wait_for(lambda: service.snapshot().buffered_count == 100))
        time.sleep(0.08)
        self.assertLess(len(delivered), 30)


if __name__ == "__main__":
    unittest.main()
