#!/usr/bin/env python3
"""Fake-only Logcat Milestone 2 update, analysis, and GUI acceptance."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_gui_smoke import isolated_smoke_environment
from scripts.run_logcat_investigator_smoke import (
    FakeProcessFactory,
    event,
    no_default_blue,
    pump,
    pump_for,
    pump_until,
)


PLUGIN_ID = "susadb.logcat-investigator"


def line(sequence, tag, message, priority="E", pid=123, tid=123):
    second = sequence % 60
    return (
        f"07-30 12:00:{second:02d}.{sequence % 1000:03d} "
        f"{pid:5d} {tid:5d} {priority} {tag}: {message}\n"
    ).encode()


def old_package(directory):
    source = ROOT / "plugins/official/logcat_investigator"
    target = Path(directory) / "logcat investigator 0.1.0"
    target.mkdir()
    manifest = json.loads(
        (source / "manifest.json").read_text(encoding="utf-8")
    )
    manifest["version"] = "0.1.0"
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (target / "plugin.py").write_text(
        (source / "plugin.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        "# Synthetic installed Logcat Investigator 0.1.0\n",
        encoding="utf-8",
    )
    return target


def main():
    import customtkinter as ctk

    from app.core.device import Device
    from app.gui.main_window import SusADBWindow
    from app.modules.logcat import LogcatEventKind

    errors = []
    geometry_measurements = []
    throughput = {}
    with tempfile.TemporaryDirectory() as temporary, isolated_smoke_environment(
        temporary
    ):
        app = SusADBWindow()
        app._deferred_started = True
        app.report_callback_exception = (
            lambda kind, value, trace: errors.append((kind.__name__, str(value)))
        )

        # A real installed 0.1.0 package follows the normal explicit update path.
        self_contained_old = old_package(temporary)
        assert app.plugin_store.install(self_contained_old).ok
        app.plugin_manager.refresh()
        installed = app.plugin_manager.records[PLUGIN_ID]
        old_digest = installed[1].package_digest
        assert installed[2].version == "0.1.0"
        assert app.plugin_manager.approve(
            PLUGIN_ID, installed[2].requested_capabilities
        ).ok
        assert app.plugin_manager.enable(PLUGIN_ID).ok
        assert app.plugin_manager.load(PLUGIN_ID).ok
        contribution_id = "logcat-investigator.panel"
        first_window = app.open_addon_window(contribution_id)
        assert first_window is not None
        candidate = next(
            value for value in app.plugin_manager.official()
            if value.manifest.plugin_id == PLUGIN_ID
        )
        assert candidate.manifest.version == "0.2.0"
        review = app.plugin_manager.official_update_review(
            PLUGIN_ID, candidate.package_digest
        )
        assert review.ok and review.status.version_changed
        assert (
            review.status.installed_version,
            review.status.candidate_version,
        ) == ("0.1.0", "0.2.0")
        assert app.plugin_manager.mark_official_update_reviewed(
            PLUGIN_ID, candidate.package_digest
        ).ok
        blocked = app.plugin_manager.install_official_update(
            PLUGIN_ID, candidate.package_digest
        )
        assert not blocked.ok and "unload" in blocked.error.casefold()
        assert app.plugin_manager.unload(PLUGIN_ID).ok
        pump(app)
        assert not app.addon_window_host.is_open(contribution_id)
        assert app.plugin_manager.install_official_update(
            PLUGIN_ID, candidate.package_digest
        ).ok
        updated = app.plugin_manager.records[PLUGIN_ID]
        assert updated[2].version == "0.2.0"
        assert updated[1].package_digest != old_digest
        assert not updated[2].enabled
        assert not app.plugin_manager.trust.verify(
            PLUGIN_ID, updated[1].package_digest
        )
        assert app.plugin_manager.trust.approved(
            PLUGIN_ID, updated[1].package_digest
        ) == ()
        assert not app.plugin_manager.enable(PLUGIN_ID).ok
        assert app.plugin_manager.approve(
            PLUGIN_ID, updated[2].requested_capabilities
        ).ok
        assert app.plugin_manager.enable(PLUGIN_ID).ok
        assert app.plugin_manager.load(PLUGIN_ID).ok
        window = app.open_addon_window(contribution_id)
        panel = app.addon_window_host.frames[contribution_id]
        service = panel.capture_service
        factory = FakeProcessFactory()
        service.process_factory = factory

        device = Device("ANALYSIS-SERIAL", state="device", model="Analysis Fixture")
        app.devices.cache.update((device,))
        app.devices.selected_serial = device.serial
        app._apply_devices([device])
        assert pump_until(
            app, lambda: str(panel.start_button.cget("state")) == "normal"
        )
        panel.start_button.invoke()
        assert pump_until(app, lambda: len(factory.calls) == 1)
        process = factory.processes[0]

        # Source buffer progression remains responsive and bounded.
        source_started = time.perf_counter()
        for index in range(1, 10_001):
            process.stdout.feed(
                line(index, "Demo", f"ordinary message {index}", "I")
            )
        assert pump_until(
            app, lambda: service.snapshot().buffered_count == 10_000, timeout=30
        ), service.snapshot().buffered_count
        assert pump_until(
            app,
            lambda: service.analysis_service.snapshot().processed_record_count
            >= 10_000,
            timeout=30,
        ), service.analysis_service.snapshot().processed_record_count
        assert service.analysis_service.snapshot().processed_record_count == 10_000
        throughput["source_10000_seconds"] = round(
            time.perf_counter() - source_started, 4
        )
        source_counts = (0, 1, 100, 1_000, 10_000)
        assert source_counts == (0, 1, 100, 1_000, 10_000)

        panel.clear_button.invoke()
        assert pump_until(
            app,
            lambda: (
                service.snapshot().buffered_count == 0
                and service.analysis_service.snapshot().unique_event_count == 0
            ),
        )

        sequence = 10_001

        def feed(tag, message, priority="E", pid=123, tid=123):
            nonlocal sequence
            process.stdout.feed(
                line(sequence, tag, message, priority, pid=pid, tid=tid)
            )
            sequence += 1

        # Every deterministic detector and multi-line reconstruction path.
        feed("AndroidRuntime", "FATAL EXCEPTION: main", pid=321, tid=321)
        feed("AndroidRuntime", "Process: com.demo.java, PID: 321", pid=321, tid=321)
        feed(
            "AndroidRuntime",
            "java.lang.IllegalStateException: fixture failure",
            pid=321,
            tid=321,
        )
        feed(
            "AndroidRuntime",
            "    at com.demo.java.Main.run(Main.java:42)",
            pid=321,
            tid=321,
        )
        feed(
            "AndroidRuntime",
            "Caused by: java.lang.RuntimeException: nested",
            pid=321,
            tid=321,
        )
        feed("Demo", "java boundary", "I")
        feed(
            "libc",
            "Fatal signal 11 (SIGSEGV), code 1, fault addr 0x12345678, "
            "pid 401, tid 402",
            "F",
            401,
            402,
        )
        feed(
            "DEBUG",
            "pid: 401, tid: 402, name: worker  >>> com.demo.native <<<",
            "F",
            401,
            402,
        )
        feed("DEBUG", "Abort message: 'native fixture'", "F", 401, 402)
        feed("DEBUG", "backtrace:", "F", 401, 402)
        feed(
            "DEBUG",
            "    #00 pc 000000001234abcd /data/app/libdemo.so "
            "(demo_crash+0x44)",
            "F",
            401,
            402,
        )
        feed("Demo", "native boundary", "I")
        feed("ActivityManager", "ANR in com.demo.anr", pid=100, tid=100)
        feed(
            "ActivityManager",
            "Reason: Input dispatching timed out",
            pid=100,
            tid=100,
        )
        feed("Demo", "anr boundary", "I")
        feed("Binder", "java.lang.SecurityException: caller rejected", pid=501)
        feed(
            "ActivityManager",
            "Permission Denial: requires android.permission.CAMERA",
            pid=502,
        )
        feed(
            "auditd",
            'avc: denied { read } for comm="demo" '
            "scontext=u:r:untrusted_app:s0 "
            "tcontext=u:object_r:secret:s0 tclass=file",
            "W",
            503,
        )
        feed(
            "ActivityManager",
            "Process com.demo.ended (pid 504) has died",
            "I",
            100,
        )
        detector_started = time.perf_counter()
        assert pump_until(
            app,
            lambda: {
                value.kind for value
                in service.analysis_service.snapshot().events
            }
            >= set(LogcatEventKind),
            timeout=10,
        )
        throughput["detector_batch_seconds"] = round(
            time.perf_counter() - detector_started, 4
        )

        # Pause affects transcript presentation only; grouped occurrences advance.
        panel.pause_button.invoke()
        assert pump_until(
            app,
            lambda: (
                service.snapshot().state.value == "view-paused"
                and panel.last_snapshot.state.value == "view-paused"
                and "capture and analysis continue in memory"
                in panel.footer.cget("text")
            ),
        )
        paused_text = panel.transcript.read()
        before_occurrences = (
            service.analysis_service.snapshot().total_occurrence_count
        )
        for _index in range(200):
            feed(
                "ActivityManager",
                "Permission Denial: requires android.permission.CAMERA",
                pid=502,
            )
        assert pump_until(
            app,
            lambda: service.analysis_service.snapshot().total_occurrence_count
            >= before_occurrences + 200,
            timeout=10,
        )
        assert panel.transcript.read() == paused_text
        assert "capture and analysis continue in memory" in panel.footer.cget("text")
        panel.pause_button.invoke()
        assert pump_until(app, lambda: service.snapshot().state.value == "running")

        # Capacity, oldest-discard, dropped count, and 1,000-event virtualization.
        unique_started = time.perf_counter()
        for index in range(1_001):
            feed(
                "ActivityManager",
                "Permission Denial: requires "
                f"android.permission.SYNTHETIC_{index}",
                pid=600,
            )
        assert pump_until(
            app,
            lambda: (
                service.analysis_service.snapshot().unique_event_count == 1_000
                and service.analysis_service.snapshot().dropped_event_groups > 0
            ),
            timeout=15,
        )
        for _index in range(200):
            feed(
                "ActivityManager",
                "Permission Denial: requires android.permission.SYNTHETIC_1000",
                pid=600,
            )
        assert pump_until(
            app,
            lambda: service.analysis_service.snapshot().total_occurrence_count
            > service.analysis_service.snapshot().unique_event_count,
            timeout=10,
        )
        throughput["events_1000_seconds"] = round(
            time.perf_counter() - unique_started, 4
        )
        analysis = service.analysis_service.snapshot()
        assert analysis.total_occurrence_count > analysis.unique_event_count
        assert len(analysis.events) == 1_000

        # Events are lazy until requested, then filter and detail surfaces are local.
        assert panel.events_page is None
        panel.events_view_button.invoke()
        pump(app)
        assert panel.view_mode == "Events"
        assert panel.events_page is not None
        assert len(panel.event_timeline.events) == 1_000
        assert "Unique: 1000" in panel.event_counts.cget("text")
        panel.event_kind_filter.set("Permission Denial")
        panel.apply_analysis_filters()
        assert panel.last_analysis_snapshot.visible_event_count <= 1_000
        panel.event_text_filter.insert(0, "SYNTHETIC_1000")
        panel.apply_analysis_filters()
        assert panel.last_analysis_snapshot.visible_event_count == 1
        panel.reset_analysis_button.invoke()
        assert panel.last_analysis_snapshot.visible_event_count == 1_000

        selected = panel.event_timeline.events[0]
        panel.view_event_details(selected)
        assert selected.event_id in panel.event_details.read()
        assert panel.event_details.read_only
        assert panel.event_stack.read_only
        assert panel.event_context.read_only
        panel.event_details.focus_for_reading()
        panel.event_details.select_all()
        assert panel.event_details._textbox.tag_ranges("sel")
        assert panel.event_details.copy_selection() == "break"
        panel.event_context._textbox.yview_moveto(0.5)
        panel.event_context._keyboard_scroll(
            event(panel.event_context._textbox, keysym="Home")
        )
        panel.event_context._keyboard_scroll(
            event(panel.event_context._textbox, keysym="End")
        )

        timeline = panel.event_timeline
        timeline.canvas.yview_moveto(0)
        pump(app)
        timeline_start = timeline.canvas.yview()
        timeline.scroll_router._wheel(event(timeline.canvas, num=5))
        pump(app)
        timeline_after_wheel = timeline.canvas.yview()
        assert timeline_after_wheel != timeline_start
        timeline.scroll_router._key(event(timeline.canvas, keysym="End"))
        pump(app)
        assert timeline.canvas.yview()[1] > 0.999
        timeline.scroll_router._key(event(timeline.canvas, keysym="Home"))
        pump(app)
        assert timeline.canvas.yview()[0] < 0.001

        # Current context navigation does not mutate transcript filters.
        filter_before = service.snapshot().filter
        assert panel.show_in_transcript(selected)
        assert panel.view_mode == "Transcript"
        assert "EVENT CONTEXT START" in panel.transcript.read()
        assert service.snapshot().filter == filter_before
        assert panel.return_to_live_view()

        # Roll the selected context out while retaining the bounded event group.
        for index in range(10_050):
            feed("Demo", f"rollover message {index}", "I", pid=700)
        assert pump_until(
            app,
            lambda: service.snapshot().dropped_records >= 1_000,
            timeout=20,
        )
        assert not panel.show_in_transcript(selected)
        assert (
            panel.footer.cget("text")
            == "Context is no longer present in the bounded Logcat buffer."
        )

        # Wide/compact layouts and all requested scaling values remain reachable.
        for scale in (1.0, 1.25, 1.5):
            ctk.set_widget_scaling(scale)
            pump_for(app, 0.8)
            for width, height in (
                (900, 650),
                (980, 700),
                (1180, 780),
                (1400, 860),
            ):
                window.geometry(f"{width}x{height}+0+0")
                panel.show_events()
                panel._show_event_list()
                pump_for(app, 0.15)
                actual_size = (window.winfo_width(), window.winfo_height())
                assert actual_size == (
                    width,
                    height,
                ), (scale, (width, height), actual_size, window.wm_geometry())
                assert panel.event_timeline.winfo_height() >= 120, (
                    scale,
                    (width, height),
                    panel.event_timeline.winfo_width(),
                    panel.event_timeline.winfo_height(),
                    panel.event_timeline.winfo_manager(),
                )
                assert panel.event_timeline.winfo_width() >= 260
                geometry_measurements.append(
                    (
                        f"{width}x{height}@{int(scale * 100)}%",
                        panel.event_timeline.winfo_width(),
                        panel.event_timeline.winfo_height(),
                        panel.event_details_frame.winfo_width(),
                        panel.event_details_frame.winfo_height(),
                    )
                )
        ctk.set_widget_scaling(1.0)
        no_default_blue(window)
        assert not errors, errors

        # Clear, close/reopen, unload, and shutdown leave no owned resource.
        panel.clear_button.invoke()
        assert pump_until(
            app,
            lambda: (
                service.snapshot().buffered_count == 0
                and service.analysis_service.snapshot().unique_event_count == 0
            ),
        )
        app.addon_window_host.close(contribution_id)
        assert pump_until(
            app,
            lambda: (
                service.worker_count == 0
                and service.callback_count == 0
                and service.process_count == 0
                and service.analysis_service.worker_count == 0
                and service.analysis_service.callback_count == 0
            ),
        )
        reopened = app.open_addon_window(contribution_id)
        reopened_panel = app.addon_window_host.frames[contribution_id]
        assert reopened is not None
        assert (
            reopened_panel.analysis_service.snapshot().unique_event_count == 0
        )
        assert app.plugin_manager.unload(PLUGIN_ID).ok
        assert not app.addon_window_host.is_open(contribution_id)
        app.shutdown()
        assert not errors, errors
        assert not any(worker.is_alive() for worker in app._background_workers)

    print(
        "logcat-investigator-analysis-smoke=PASS "
        "sizes=900x650,980x700,1180x780,1400x860 "
        "scaling=100%,125%,150% records=0,1,100,1000,10000 "
        "events=0,1,100,1000,duplicate-heavy-overflow "
        f"throughput={throughput} geometry={geometry_measurements} "
        "update-0.1.0-to-0.2.0-review-unload-new-digest-trust=PASS "
        "java-native-anr-security-permission-selinux-process-death=PASS "
        "grouping-filters-details-show-transcript-expired-context=PASS "
        "wheel-touchpad-keyboard-copy-select-compact-wide=PASS "
        "callbacks=0 bindings=0 processes=0 subscriptions=0 workers=0 "
        "no-default-blue-no-tcl-errors=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
