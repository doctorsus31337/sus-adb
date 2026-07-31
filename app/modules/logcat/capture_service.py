"""Host-owned, bounded, cancellable Logcat capture service."""

from __future__ import annotations

import os
import subprocess
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from app.modules.logcat.analysis_service import LogcatAnalysisService
from app.modules.logcat.models import (
    DEFAULT_CAPACITY,
    MAX_CAPACITY,
    MAX_STATUS_TEXT,
    MIN_CAPACITY,
    LogcatCaptureSnapshot,
    LogcatCaptureState,
    LogcatFilter,
)
from app.modules.logcat.parser import ThreadtimeParser


@dataclass(frozen=True, slots=True)
class LogcatServiceResult:
    ok: bool
    snapshot: LogcatCaptureSnapshot
    error: str = ""
    argv: tuple[str, ...] = ()


class CaptureSubscription:
    """Idempotent cancellation handle for one capture subscriber."""

    def __init__(self, cancel: Callable[[], None]):
        self._cancel = cancel
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            callback, self._cancel = self._cancel, None
        if callback is not None:
            callback()

    close = cancel


class LogcatCaptureService:
    """Own exactly one selected-device Logcat process and its bounded records."""

    ACTIVE = frozenset(
        (
            LogcatCaptureState.STARTING,
            LogcatCaptureState.RUNNING,
            LogcatCaptureState.VIEW_PAUSED,
            LogcatCaptureState.STOPPING,
        )
    )

    def __init__(
        self,
        adb_path: str,
        *,
        process_factory: Callable[..., object] | None = None,
        dispatcher: Callable[..., None] | None = None,
        capacity: int = DEFAULT_CAPACITY,
        batch_interval: float = 0.075,
        stop_timeout: float = 2.0,
        parser: ThreadtimeParser | None = None,
        analysis_service: LogcatAnalysisService | None = None,
    ):
        if not MIN_CAPACITY <= int(capacity) <= MAX_CAPACITY:
            raise ValueError(
                f"Logcat capacity must be between {MIN_CAPACITY} and {MAX_CAPACITY}."
            )
        self.adb_path = str(adb_path or "")
        self.process_factory = process_factory or subprocess.Popen
        self.dispatcher = dispatcher or (lambda callback, *args: callback(*args))
        self.capacity = int(capacity)
        self.batch_interval = max(0.02, float(batch_interval))
        self.stop_timeout = max(0.05, float(stop_timeout))
        self.parser = parser or ThreadtimeParser()
        self.analysis_service = analysis_service or LogcatAnalysisService()
        self._records = deque(maxlen=self.capacity)
        self._lock = threading.RLock()
        self._subscribers: dict[int, Callable[[LogcatCaptureSnapshot], None]] = {}
        self._next_subscriber = 0
        self._process = None
        self._threads: set[threading.Thread] = set()
        self._notify_event = threading.Event()
        self._notify_stop = threading.Event()
        self._stop_requested = False
        self._sequence = 0
        self._dropped = 0
        self._state = LogcatCaptureState.IDLE
        self._capture_serial = ""
        self._selected_serial = ""
        self._status = "Ready; capture has not started."
        self._error = ""
        self._stderr = ""
        self._filter = LogcatFilter()
        self._filter_generation = 0
        self._closed = False
        self.argv: tuple[str, ...] = ()

    @staticmethod
    def _creation_flags() -> int:
        if os.name == "nt":
            return getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return 0

    def set_selected_serial(self, serial: str) -> None:
        with self._lock:
            self._selected_serial = str(serial or "")
        self._request_publish()

    def snapshot(self) -> LogcatCaptureSnapshot:
        with self._lock:
            records = tuple(self._records)
            current_filter = self._filter
            values = {
                "state": self._state,
                "selected_serial": self._selected_serial,
                "capture_serial": self._capture_serial,
                "dropped_records": self._dropped,
                "status_text": self._status,
                "error_text": self._error,
                "filter": current_filter,
                "filter_generation": self._filter_generation,
            }
        visible = tuple(record for record in records if current_filter.matches(record))
        return LogcatCaptureSnapshot(
            records=records,
            visible_records=visible,
            **values,
        )

    def subscribe(
        self,
        callback: Callable[[LogcatCaptureSnapshot], None],
        *,
        replay: bool = True,
    ) -> CaptureSubscription:
        with self._lock:
            if self._closed:
                return CaptureSubscription(lambda: None)
            self._next_subscriber += 1
            key = self._next_subscriber
            self._subscribers[key] = callback
        if replay:
            self.dispatcher(self._deliver, callback, self.snapshot())

        def cancel() -> None:
            with self._lock:
                self._subscribers.pop(key, None)

        return CaptureSubscription(cancel)

    @staticmethod
    def _deliver(callback, snapshot) -> None:
        callback(snapshot)

    def _publish(self) -> None:
        snapshot = self.snapshot()
        self.analysis_service.consume_capture_snapshot(snapshot)
        with self._lock:
            callbacks = tuple(self._subscribers.values())
        for callback in callbacks:
            self.dispatcher(self._deliver, callback, snapshot)

    def _request_publish(self) -> None:
        self._notify_event.set()
        if not any(thread.name.endswith("-notify") for thread in self._threads):
            self._publish()

    def _notifier(self) -> None:
        try:
            while not self._notify_stop.is_set():
                self._notify_event.wait(self.batch_interval)
                self._notify_event.clear()
                self._publish()
        finally:
            self._publish()
            self._thread_finished()

    def start(self, serial: str) -> LogcatServiceResult:
        copied_serial = str(serial or "").strip()
        with self._lock:
            if self._closed:
                return LogcatServiceResult(False, self.snapshot(), "Capture is closed.")
            if self._state in self.ACTIVE:
                return LogcatServiceResult(
                    False, self.snapshot(), "A Logcat capture is already active.", self.argv
                )
            if not copied_serial:
                return LogcatServiceResult(
                    False, self.snapshot(), "Select an explicit device before capture."
                )
            if not self.adb_path:
                return LogcatServiceResult(
                    False, self.snapshot(), "ADB is unavailable; capture cannot start."
                )
            self._records.clear()
            self.analysis_service.clear()
            self._dropped = 0
            self._sequence = 0
            self._capture_serial = copied_serial
            self._selected_serial = copied_serial
            self._state = LogcatCaptureState.STARTING
            self._status = f"Starting capture for {copied_serial}."
            self._error = ""
            self._stderr = ""
            self._stop_requested = False
            self._notify_stop.clear()
            self.argv = (
                self.adb_path,
                "-s",
                copied_serial,
                "logcat",
                "-v",
                "threadtime",
            )
        self._publish()
        try:
            process = self.process_factory(
                self.argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                bufsize=0,
                creationflags=self._creation_flags(),
                shell=False,
            )
        except Exception as exc:
            with self._lock:
                self._state = LogcatCaptureState.FAILED
                self._error = f"Unable to start Logcat: {exc}"[:MAX_STATUS_TEXT]
                self._status = "Capture failed to start."
                self._process = None
            self._publish()
            return LogcatServiceResult(False, self.snapshot(), self._error, self.argv)
        with self._lock:
            self._process = process
            self._state = LogcatCaptureState.RUNNING
            self._status = f"Capturing device logs from {copied_serial}."
            threads = (
                threading.Thread(
                    target=self._stdout_reader,
                    name="sus-logcat-stdout",
                    daemon=True,
                ),
                threading.Thread(
                    target=self._stderr_reader,
                    name="sus-logcat-stderr",
                    daemon=True,
                ),
                threading.Thread(
                    target=self._monitor_process,
                    name="sus-logcat-monitor",
                    daemon=True,
                ),
                threading.Thread(
                    target=self._notifier,
                    name="sus-logcat-notify",
                    daemon=True,
                ),
            )
            self._threads.update(threads)
        for thread in threads:
            thread.start()
        self._request_publish()
        return LogcatServiceResult(True, self.snapshot(), argv=self.argv)

    @staticmethod
    def _read_lines(stream):
        if stream is None:
            return
        if hasattr(stream, "readline"):
            while True:
                value = stream.readline()
                if value in (b"", ""):
                    break
                yield value
            return
        yield from stream

    def _stdout_reader(self) -> None:
        try:
            process = self._process
            previous = None
            for line in self._read_lines(getattr(process, "stdout", None)):
                with self._lock:
                    if self._closed:
                        break
                    self._sequence += 1
                    record = self.parser.parse(line, self._sequence, previous)
                    if len(self._records) == self.capacity:
                        self._dropped += 1
                    self._records.append(record)
                    previous = record
                self._notify_event.set()
        except Exception as exc:
            self._reader_failed("stdout", exc)
        finally:
            self._thread_finished()

    def _stderr_reader(self) -> None:
        try:
            process = self._process
            for line in self._read_lines(getattr(process, "stderr", None)):
                text = self.parser.decode(line)
                with self._lock:
                    self._stderr = (self._stderr + "\n" + text).strip()[
                        -MAX_STATUS_TEXT:
                    ]
        except Exception as exc:
            self._reader_failed("stderr", exc)
        finally:
            self._thread_finished()

    def _reader_failed(self, source: str, exc: Exception) -> None:
        with self._lock:
            if self._stop_requested or self._closed:
                return
            self._state = LogcatCaptureState.FAILED
            self._error = f"Logcat {source} reader failed: {exc}"[:MAX_STATUS_TEXT]
            self._status = "Capture failed."
        self._terminate_owned_process()
        self._request_publish()

    def _monitor_process(self) -> None:
        try:
            process = self._process
            returncode = process.wait() if process is not None else 0
            with self._lock:
                requested = self._stop_requested or self._closed
                if not requested and self._state is not LogcatCaptureState.FAILED:
                    detail = f"Logcat exited unexpectedly with code {returncode}."
                    if self._stderr:
                        detail += f" {self._stderr}"
                    self._state = LogcatCaptureState.FAILED
                    self._error = detail[:MAX_STATUS_TEXT]
                    self._status = "Capture ended unexpectedly."
        except Exception as exc:
            self._reader_failed("process monitor", exc)
        finally:
            self._request_publish()
            self._thread_finished()

    def _thread_finished(self) -> None:
        current = threading.current_thread()
        with self._lock:
            self._threads.discard(current)

    def pause_view(self) -> LogcatServiceResult:
        with self._lock:
            if self._state is not LogcatCaptureState.RUNNING:
                return LogcatServiceResult(
                    False, self.snapshot(), "View can pause only during capture.", self.argv
                )
            self._state = LogcatCaptureState.VIEW_PAUSED
            self._status = "View paused; capture continues in memory."
        self._request_publish()
        return LogcatServiceResult(True, self.snapshot(), argv=self.argv)

    def resume_view(self) -> LogcatServiceResult:
        with self._lock:
            if self._state is not LogcatCaptureState.VIEW_PAUSED:
                return LogcatServiceResult(
                    False, self.snapshot(), "View is not paused.", self.argv
                )
            self._state = LogcatCaptureState.RUNNING
            self._status = f"Capturing device logs from {self._capture_serial}."
        self._request_publish()
        return LogcatServiceResult(True, self.snapshot(), argv=self.argv)

    def set_filter(self, value: LogcatFilter) -> LogcatCaptureSnapshot:
        if not isinstance(value, LogcatFilter):
            raise TypeError("Logcat filter must be an immutable LogcatFilter.")
        with self._lock:
            self._filter = value
            self._filter_generation += 1
        self._request_publish()
        return self.snapshot()

    def clear(self) -> LogcatCaptureSnapshot:
        with self._lock:
            self._records.clear()
            self._dropped = 0
            self._status = (
                "View and host memory cleared; Android Logcat was not cleared."
            )
        self.analysis_service.clear()
        self._request_publish()
        return self.snapshot()

    def _terminate_owned_process(self) -> None:
        with self._lock:
            process = self._process
        if process is None:
            return
        try:
            if getattr(process, "poll", lambda: None)() is None:
                process.terminate()
            process.wait(timeout=self.stop_timeout)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=self.stop_timeout)
            except Exception:
                pass
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def stop(self) -> LogcatServiceResult:
        with self._lock:
            if self._state is LogcatCaptureState.CLOSED:
                return LogcatServiceResult(True, self.snapshot(), argv=self.argv)
            if self._process is None and self._state not in self.ACTIVE:
                if self._state is not LogcatCaptureState.FAILED:
                    self._state = LogcatCaptureState.STOPPED
                    self._status = "Capture stopped."
                self._publish()
                return LogcatServiceResult(True, self.snapshot(), argv=self.argv)
            self._stop_requested = True
            self._state = LogcatCaptureState.STOPPING
            self._status = "Stopping owned Logcat capture."
        self._publish()
        self._terminate_owned_process()
        process = self._process
        for stream_name in ("stdout", "stderr"):
            stream = getattr(process, stream_name, None) if process is not None else None
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass
        current = threading.current_thread()
        for thread in tuple(self._threads):
            if thread is not current and not thread.name.endswith("-notify"):
                thread.join(self.stop_timeout)
        self._notify_stop.set()
        self._notify_event.set()
        for thread in tuple(self._threads):
            if thread is not current:
                thread.join(self.stop_timeout)
        with self._lock:
            self._process = None
            if not self._closed:
                self._state = LogcatCaptureState.STOPPED
                self._status = "Capture stopped."
            records = tuple(self._records)
        self.analysis_service.flush(records)
        self._publish()
        return LogcatServiceResult(True, self.snapshot(), argv=self.argv)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
        self.stop()
        with self._lock:
            self._closed = True
            self._records.clear()
            self._dropped = 0
            self._capture_serial = ""
            self._selected_serial = ""
            self._stderr = ""
            self._error = ""
            self._status = "Capture closed; sensitive records cleared."
            self._state = LogcatCaptureState.CLOSED
            callbacks = tuple(self._subscribers.values())
            self._subscribers.clear()
        self.analysis_service.close()
        snapshot = self.snapshot()
        for callback in callbacks:
            self.dispatcher(self._deliver, callback, snapshot)

    cleanup = close

    @property
    def worker_count(self) -> int:
        with self._lock:
            return sum(thread.is_alive() for thread in self._threads)

    @property
    def callback_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    @property
    def process_count(self) -> int:
        with self._lock:
            process = self._process
        if process is None:
            return 0
        try:
            return int(process.poll() is None)
        except Exception:
            return 1
