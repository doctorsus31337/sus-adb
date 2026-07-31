#!/usr/bin/env python3
"""Fake-only Logcat Investigator lifecycle, streaming, and GUI acceptance."""

from __future__ import annotations

import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_gui_smoke import isolated_smoke_environment


class FakeStream:
    EOF = object()

    def __init__(self):
        self.values = queue.Queue()
        self.closed = False

    def feed(self, value):
        self.values.put(value)

    def readline(self):
        value = self.values.get()
        return b"" if value is self.EOF else value

    def close(self):
        if not self.closed:
            self.closed = True
            self.values.put(self.EOF)


class FakeProcess:
    def __init__(self):
        self.stdout = FakeStream()
        self.stderr = FakeStream()
        self.returncode = None
        self.finished = threading.Event()
        self.terminate_count = 0
        self.kill_count = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if not self.finished.wait(timeout):
            raise subprocess.TimeoutExpired("fake-logcat", timeout)
        return self.returncode

    def terminate(self):
        self.terminate_count += 1
        self.exit(0)

    def kill(self):
        self.kill_count += 1
        self.exit(-9)

    def exit(self, returncode):
        if self.returncode is None:
            self.returncode = returncode
            self.stdout.close()
            self.stderr.close()
            self.finished.set()


class FakeProcessFactory:
    def __init__(self):
        self.calls = []
        self.processes = []

    def __call__(self, argv, **kwargs):
        process = FakeProcess()
        self.calls.append((tuple(argv), kwargs))
        self.processes.append(process)
        return process


def pump(widget):
    widget.update_idletasks()
    widget.update()
    widget.update_idletasks()


def pump_until(widget, condition, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pump(widget)
        if condition():
            return True
        time.sleep(0.005)
    return bool(condition())


def pump_for(widget, duration):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        pump(widget)
        time.sleep(0.005)


def event(widget, *, num=None, delta=0, keysym="", char="", state=0):
    return SimpleNamespace(
        widget=widget,
        num=num,
        delta=delta,
        keysym=keysym,
        char=char,
        state=state,
    )


def no_default_blue(root):
    stack = [root]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        keys = getattr(widget, "keys", lambda: ())()
        for key in (
            "fg_color",
            "hover_color",
            "border_color",
            "button_color",
            "button_hover_color",
        ):
            if key not in keys:
                continue
            value = str(widget.cget(key)).casefold()
            assert "blue" not in value
            assert "#3b8ed0" not in value and "#1f6aa5" not in value


def main():
    import customtkinter as ctk

    from app.core.device import Device
    from app.gui.main_window import SusADBWindow
    from app.modules.logcat import LogcatCaptureState

    errors = []
    measurements = []
    with tempfile.TemporaryDirectory() as temporary, isolated_smoke_environment(
        temporary
    ):
        app = SusADBWindow()
        app._deferred_started = True
        app.report_callback_exception = (
            lambda kind, value, trace: errors.append((kind.__name__, str(value)))
        )
        item = next(
            value for value in app.plugin_manager.official()
            if value.manifest.plugin_id == "susadb.logcat-investigator"
        )
        plugin_id = item.manifest.plugin_id
        assert len(app.plugin_manager.official()) == 7
        assert app.plugin_manager.install_official(
            plugin_id, item.package_digest
        ).ok
        assert not app.plugin_manager.trust.verify(plugin_id, item.package_digest)
        assert not app.plugin_manager.records[plugin_id][2].enabled
        assert not app.plugin_manager.load(plugin_id).ok
        assert app.plugin_manager.approve(
            plugin_id, item.manifest.requested_capabilities
        ).ok
        assert not app.plugin_manager.records[plugin_id][2].enabled
        assert app.plugin_manager.enable(plugin_id).ok
        assert not app.plugin_registry.by_plugin(plugin_id)
        assert app.plugin_manager.load(plugin_id).ok
        contribution = app.plugin_registry.by_plugin(plugin_id)[0]
        assert contribution.contribution_id == "logcat-investigator.panel"
        assert not app.addon_window_host.is_open(contribution.contribution_id)
        window = app.open_addon_window(contribution.contribution_id)
        assert window is not None
        panel = app.addon_window_host.frames[contribution.contribution_id]
        service = panel.capture_service
        factory = FakeProcessFactory()
        service.process_factory = factory
        pump(app)
        assert service.snapshot().state is LogcatCaptureState.IDLE
        assert not factory.calls
        assert str(panel.start_button.cget("state")) == "disabled"
        assert "Selected: None" in panel.status.cget("text")

        first = Device("SERIAL-ONE", state="device", model="Fixture One")
        second = Device("SERIAL-TWO", state="device", model="Fixture Two")
        app.devices.cache.update((first, second))
        app.devices.selected_serial = first.serial
        app._apply_devices([first, second])
        assert pump_until(
            app, lambda: str(panel.start_button.cget("state")) == "normal"
        )
        panel.start_button.invoke()
        assert pump_until(
            app, lambda: service.snapshot().state is LogcatCaptureState.RUNNING
        )
        assert len(factory.calls) == 1
        argv, kwargs = factory.calls[0]
        assert argv == (
            app.devices.adb.adb_path,
            "-s",
            "SERIAL-ONE",
            "logcat",
            "-v",
            "threadtime",
        )
        assert kwargs["shell"] is False
        assert not service.start("SERIAL-ONE").ok
        process = factory.processes[0]

        def feed_range(start, stop):
            for index in range(start, stop):
                priority = b"E" if index % 10 == 0 else b"I"
                process.stdout.feed(
                    b"07-30 12:34:56.789  123  456 "
                    + priority
                    + b" DemoTag: message "
                    + str(index).encode()
                    + b"\n"
                )

        counts = []
        feed_range(0, 1)
        assert pump_until(app, lambda: service.snapshot().buffered_count == 1)
        counts.append((1, service.snapshot().visible_count))
        feed_range(1, 100)
        assert pump_until(app, lambda: service.snapshot().buffered_count == 100)
        assert pump_until(app, lambda: "message 99" in panel.transcript.read())
        counts.append((100, service.snapshot().visible_count))

        before_pause = panel.transcript.read()
        panel.pause_button.invoke()
        assert pump_until(
            app,
            lambda: (
                service.snapshot().state is LogcatCaptureState.VIEW_PAUSED
                and panel.pause_button.cget("text") == "Resume View"
            ),
        )
        assert "capture and analysis continue in memory" in panel.footer.cget("text")
        feed_range(100, 1_000)
        assert pump_until(app, lambda: service.snapshot().buffered_count == 1_000)
        pump(app)
        assert panel.transcript.read() == before_pause
        panel.pause_button.invoke()
        assert pump_until(
            app, lambda: service.snapshot().state is LogcatCaptureState.RUNNING
        )
        assert pump_until(app, lambda: "message 999" in panel.transcript.read())
        counts.append((1_000, service.snapshot().visible_count))

        feed_range(1_000, 10_000)
        assert pump_until(
            app, lambda: service.snapshot().buffered_count == 10_000, timeout=15
        )
        assert pump_until(
            app, lambda: "message 9999" in panel.transcript.read(), timeout=15
        )
        counts.append((10_000, service.snapshot().visible_count))
        feed_range(10_000, 10_100)
        assert pump_until(
            app, lambda: service.snapshot().dropped_records == 100, timeout=10
        )
        assert service.snapshot().buffered_count == 10_000
        assert pump_until(
            app,
            lambda: "Dropped: 100" in panel.status.cget("text"),
            timeout=10,
        )

        panel.priority.set("Error")
        panel.apply_filters()
        assert pump_until(app, lambda: service.snapshot().visible_count == 1_000)
        panel.priority.set("Verbose")
        panel.tag_filter.insert(0, "demotag")
        panel.apply_filters()
        assert pump_until(app, lambda: service.snapshot().visible_count == 10_000)
        panel.pid_filter.insert(0, "bad")
        assert not panel.apply_filters()
        assert "exact non-negative integer" in panel.footer.cget("text")
        panel.pid_filter.delete(0, "end")
        panel.pid_filter.insert(0, "123")
        panel.message_filter.insert(0, "message 10099")
        panel.apply_filters()
        assert pump_until(app, lambda: service.snapshot().visible_count == 1)
        panel.reset_filters()
        assert pump_until(app, lambda: service.snapshot().visible_count == 10_000)

        transcript = panel.transcript
        transcript.focus_for_reading()
        transcript.select_all()
        assert transcript._textbox.tag_ranges("sel")
        assert transcript.copy_selection() == "break"
        assert transcript._key_pressed(event(transcript._textbox, char="x")) == "break"
        transcript._textbox.yview_moveto(0.5)
        before = transcript._textbox.yview()
        assert transcript.scroll_router._wheel(
            event(transcript._textbox, num=5)
        ) == "break"
        assert transcript._textbox.yview() != before
        transcript._keyboard_scroll(event(transcript._textbox, keysym="Next"))
        transcript._keyboard_scroll(event(transcript._textbox, keysym="Home"))
        assert transcript._textbox.yview()[0] < 0.001
        transcript._keyboard_scroll(event(transcript._textbox, keysym="End"))
        assert transcript._textbox.yview()[1] > 0.999

        app.select_device(second.serial)
        assert pump_until(
            app, lambda: "capture remains bound" in panel.device_warning.cget("text")
        )
        assert service.snapshot().capture_serial == first.serial
        assert service.argv[2] == first.serial

        calls_before = len(factory.calls)
        panel.clear_button.invoke()
        assert pump_until(app, lambda: service.snapshot().buffered_count == 0)
        assert len(factory.calls) == calls_before
        assert not panel.transcript.read().strip()
        assert pump_until(
            app,
            lambda: "Android Logcat was not cleared" in panel.footer.cget("text"),
        )

        panel.stop_button.invoke()
        assert pump_until(
            app, lambda: service.snapshot().state is LogcatCaptureState.STOPPED
        )
        assert process.terminate_count == 1
        panel.stop_capture()
        assert pump_until(app, lambda: not panel._busy)
        assert process.terminate_count == 1

        app.select_device(first.serial)
        assert pump_until(
            app, lambda: str(panel.start_button.cget("state")) == "normal"
        )
        panel.start_button.invoke()
        assert pump_until(app, lambda: len(factory.calls) == 2)
        factory.processes[1].exit(9)
        assert pump_until(
            app, lambda: service.snapshot().state is LogcatCaptureState.FAILED
        )
        assert pump_until(app, lambda: "code 9" in panel.footer.cget("text"))

        for scale in (1.0, 1.25, 1.5):
            ctk.set_widget_scaling(scale)
            pump_for(app, 1.1)
            for width, height in ((900, 650), (980, 700), (1180, 780), (1400, 860)):
                window.geometry(f"{width}x{height}+0+0")
                pump(app)
                actual_size = (window.winfo_width(), window.winfo_height())
                assert actual_size == (width, height), (
                    scale,
                    (width, height),
                    actual_size,
                    window.wm_geometry(),
                )
                assert panel.transcript.winfo_height() >= 180, (
                    scale,
                    (width, height),
                    panel.transcript.winfo_height(),
                )
                assert (
                    panel.transcript.winfo_rooty() + panel.transcript.winfo_height()
                    <= panel.footer.winfo_rooty() + 2
                )
                measurements.append(
                    (
                        f"{width}x{height}@{int(scale * 100)}%",
                        panel.status.winfo_height(),
                        panel.transcript.winfo_height(),
                        panel.footer.winfo_height(),
                    )
                )
        ctk.set_widget_scaling(1.0)
        no_default_blue(window)
        assert not errors, errors

        app.addon_window_host.close(contribution.contribution_id)
        assert pump_until(
            app,
            lambda: (
                service.worker_count == 0
                and service.callback_count == 0
                and service.process_count == 0
            ),
        )
        assert service.snapshot().buffered_count == 0
        assert not app.addon_window_host.is_open(contribution.contribution_id)
        reopened = app.open_addon_window(contribution.contribution_id)
        assert reopened is not None
        reopened_panel = app.addon_window_host.frames[contribution.contribution_id]
        assert reopened_panel.capture_service.snapshot().state is LogcatCaptureState.IDLE
        assert len(factory.calls) == 2
        assert app.plugin_manager.unload(plugin_id).ok
        assert not app.addon_window_host.is_open(contribution.contribution_id)
        assert pump_until(
            app,
            lambda: (
                reopened_panel.capture_service.worker_count == 0
                and reopened_panel.capture_service.callback_count == 0
                and reopened_panel.capture_service.process_count == 0
            ),
        )
        app.shutdown()
        assert not errors, errors
        assert not any(worker.is_alive() for worker in app._background_workers)

    print(
        "logcat-investigator-smoke=PASS "
        "sizes=900x650,980x700,1180x780,1400x860 "
        "scaling=100%,125%,150% records=0,1,100,1000,10000,overflow "
        f"counts={counts} measurements={measurements} "
        "lifecycle-install-trust-approve-enable-load-open=PASS "
        "no-device-start-duplicate-batching-pause-resume-stop-clear=PASS "
        "priority-tag-pid-message-reset-readonly-copy-select-scroll=PASS "
        "device-change-close-reopen-unload-shutdown-cleanup=PASS "
        "callbacks=0 bindings=0 processes=0 subscriptions=0 workers=0 "
        "no-default-blue-no-tcl-errors=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
