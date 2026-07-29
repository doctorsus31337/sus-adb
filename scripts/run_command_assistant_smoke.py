#!/usr/bin/env python3
"""Isolated local-only GUI acceptance for Console Command Assistant v1."""

from __future__ import annotations

import sys
import time
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import customtkinter as ctk

from app.core.command_completion import (
    CommandCompletionContext,
    CommandCompletionService,
)
from app.core.command_registry import CommandSpec
from app.core.command_router import CommandClassification
from app.gui.main_window import SusADBWindow


def bounds(widget):
    return (
        widget.winfo_rootx(), widget.winfo_rooty(),
        widget.winfo_width(), widget.winfo_height(),
    )


def pump_until(app, condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.update()
        if condition():
            return True
    return bool(condition())


def synthetic_service(count, limit=10, long=False):
    return CommandCompletionService(
        specs=tuple(
            CommandSpec(
                f"adb fixture-{index:03}",
                (
                    "A deliberately long local-only description that remains readable "
                    "without invoking any command or environment operation."
                    if long else "Synthetic local-only command"
                ),
                f"fixture.{index:03}", "ADB", "Synthetic",
            )
            for index in range(count)
        ),
        visible_limit=limit,
    )


def latency(count):
    service = synthetic_service(count)
    started = time.perf_counter()
    for _index in range(50):
        result = service.suggest("adb f")
    elapsed = (time.perf_counter() - started) * 1000 / 50
    assert result.total_count == count
    return round(elapsed, 4)


def main():
    SusADBWindow.startup_check = lambda self: None
    app = SusADBWindow()
    app.geometry("1100x700+0+0")
    app.navigate_workspace("Console")
    app.update_idletasks()
    bar = app.command_bar
    executed = []
    bar.execute_callback = executed.append
    output = app.console
    output_inner = output._textbox

    assert output.read_only
    assert "sus-companion > Ready." in output.read()
    transcript_before = output.read()
    bar._set_entry("")
    app.focus_force()
    output.focus_for_reading()
    assert pump_until(app, lambda: app.focus_get() is output_inner)
    output_inner.event_generate("<KeyPress-a>")
    assert pump_until(app, lambda: bar.entry.get() == "a")
    assert output.read() == transcript_before
    assert bar.entry.get() == "a"
    assert executed == []
    bar._refresh()
    app.update_idletasks()
    assert bar.suggestions_open
    bar.hide_suggestions()
    assert pump_until(app, lambda: not bar.suggestion_panel.winfo_ismapped())

    bar._set_entry("db")
    bar.entry.icursor(0)
    output.focus_for_reading()
    assert pump_until(app, lambda: app.focus_get() is output_inner)
    output_inner.event_generate("<KeyPress-a>")
    assert pump_until(app, lambda: bar.entry.get() == "adb")
    assert bar.entry.get() == "adb", (
        bar.entry.get(), bar.entry.index("insert")
    )
    assert output.read() == transcript_before
    assert executed == []

    output.focus_for_reading()
    for sequence in (
        "<BackSpace>", "<Delete>", "<Control-x>", "<Control-v>",
        "<<Cut>>", "<<Paste>>", "<Button-2>", "<Return>",
    ):
        output_inner.event_generate(sequence)
        app.update_idletasks()
        assert output.read() == transcript_before, sequence
    assert executed == []
    assert output._key_pressed(
        SimpleNamespace(char="\t", state=0)
    ) is None
    assert output._key_pressed(
        SimpleNamespace(char="c", state=0x0004)
    ) is None

    output_inner.tag_add("sel", "1.0", "1.8")
    assert output.copy_selection() == "break"
    assert output.clipboard_get() == "sus-comp"
    output_inner.tag_remove("sel", "1.0", "end")
    output.select_all()
    assert output_inner.tag_ranges("sel")

    output.append("programmatic line\nmultiline one\nmultiline two\n")
    assert output.read_only
    assert output.read().count("programmatic line") == 1
    with mock.patch.object(
        ctk.CTkTextbox, "insert", side_effect=RuntimeError("fixture")
    ):
        try:
            output.append("must fail")
        except RuntimeError:
            pass
        else:
            raise AssertionError("failed transcript mutation did not raise")
    assert output.read_only

    for index in range(180):
        output.append(f"stream fixture {index}\n")
    app.update_idletasks()
    output_inner.yview_moveto(.35)
    initial_yview = output_inner.yview()
    output.scroll_router._wheel(
        SimpleNamespace(widget=output_inner, delta=-1, num=None)
    )
    touchpad_yview = output_inner.yview()
    assert touchpad_yview != initial_yview
    output_inner.focus_set()
    output_inner.event_generate("<Next>")
    app.update()
    page_yview = output_inner.yview()
    assert page_yview != touchpad_yview
    output_inner.event_generate("<Up>")
    app.update()

    saved = []
    with mock.patch(
        "app.gui.main_window.FileManager.save_console",
        side_effect=saved.append,
    ):
        app.save_console()
    assert saved == [output.read()]
    app.clear_console()
    assert output.read().startswith("sus-companion > Console cleared.")
    assert output.read_only
    app.log("[DEFERRED] synthetic diagnostics")
    worker = threading.Thread(
        target=app.terminal._write_line, args=("[STREAM] synthetic line",)
    )
    worker.start()
    worker.join()
    time.sleep(.03)
    app.update()
    assert output.read().count("[DEFERRED] synthetic diagnostics") == 1
    assert output.read().count("[STREAM] synthetic line") == 1

    entry_inner = getattr(bar.entry, "_entry", bar.entry)

    def select_all_entry(sequence="<Control-a>"):
        entry_inner.focus_set()
        app.update()
        if sequence == "<Control-a>":
            entry_inner.event_generate("<KeyPress>", keysym="a", state=0x0004)
        elif sequence == "<Control-A>":
            entry_inner.event_generate("<KeyPress>", keysym="A", state=0x0005)
        else:
            entry_inner.event_generate(sequence)
        app.update()
        return (
            entry_inner.selection_present(),
            entry_inner.index("sel.first") if entry_inner.selection_present() else None,
            entry_inner.index("sel.last") if entry_inner.selection_present() else None,
            entry_inner.index("insert"),
        )

    history_before_select_all = bar.history.entries()
    bar._set_entry("adb devices -l")
    selection = select_all_entry()
    assert selection == (
        True, 0, len("adb devices -l"), len("adb devices -l")
    ), selection
    assert bar.entry.get() == "adb devices -l"
    assert executed == []
    assert bar.history.entries() == history_before_select_all

    bar._set_entry("")
    assert select_all_entry() == (False, None, None, 0)
    assert bar.entry.get() == ""

    bar._set_entry("adb reboot bootloader")
    bar._refresh()
    highlighted = bar.result.suggestions[bar.selected_index]
    select_all_entry()
    entry_inner.event_generate("<KeyPress-a>")
    entry_inner.event_generate("<KeyRelease-a>")
    time.sleep((bar.REFRESH_DELAY_MS + 20) / 1000)
    app.update()
    assert bar.entry.get() == "a"
    assert bar.suggestions_open
    assert bar.result.suggestions[0].command_text.startswith("adb")
    assert highlighted.command_text != bar.entry.get()
    assert executed == []
    assert bar.history.entries() == history_before_select_all

    for sequence in ("<BackSpace>", "<Delete>"):
        bar._set_entry("adb shell")
        select_all_entry("<Control-A>")
        entry_inner.event_generate(sequence)
        app.update_idletasks()
        assert bar.entry.get() == "", sequence
        assert executed == []

    output_inner.tag_remove("sel", "1.0", "end")
    bar._set_entry("entry selection")
    select_all_entry()
    assert not output_inner.tag_ranges("sel")
    entry_inner.selection_clear()
    output.select_all()
    assert output_inner.tag_ranges("sel")
    assert not entry_inner.selection_present()
    output_inner.tag_remove("sel", "1.0", "end")

    bar._set_entry("")
    entry_inner.event_generate("<Control-space>")
    app.update_idletasks()
    assert bar.suggestions_open
    bar.hide_suggestions()

    bar._set_entry("copy fixture")
    select_all_entry()
    entry_inner.event_generate("<Control-c>")
    app.update_idletasks()
    assert bar.clipboard_get() == "copy fixture"
    entry_inner.event_generate("<Control-x>")
    app.update_idletasks()
    assert bar.entry.get() == ""
    bar.clipboard_clear()
    bar.clipboard_append("paste fixture")
    entry_inner.event_generate("<Control-v>")
    app.update_idletasks()
    assert bar.entry.get() == "paste fixture"
    assert executed == []

    macos_sequences = bar._select_all_sequences("darwin")
    assert macos_sequences == (
        "<Control-a>", "<Control-A>", "<Command-a>", "<Command-A>",
    )
    assert bar._select_all_sequences("linux") == ("<Control-a>", "<Control-A>")
    bar._set_entry("")
    bar.hide_suggestions()

    contexts = (
        CommandCompletionContext(),
        CommandCompletionContext("USB-SERIAL", "device"),
        CommandCompletionContext("192.0.2.10:5555", "device"),
        CommandCompletionContext("USB-SERIAL", "unauthorized"),
        CommandCompletionContext("USB-SERIAL", "offline"),
        CommandCompletionContext(
            "USB-SERIAL", "device", "org.example.fixture", "posix"
        ),
        CommandCompletionContext(
            tool_availability=(
                ("adb", False), ("frida", False), ("objection", False)
            )
        ),
    )
    context_results = []
    for context in contexts:
        bar.context_provider = lambda value=context: value
        bar._set_entry("adb")
        bar._refresh()
        app.update_idletasks()
        assert bar.suggestions_open
        context_results.append((context.selected_device_state, bar.result.context_note))

    bar.context_provider = CommandCompletionContext
    for query, expected in (
        ("a", "adb"),
        ("adb re", "adb reboot"),
        ("adb reboot b", "adb reboot bootloader"),
    ):
        bar._set_entry(query)
        bar._refresh()
        app.update_idletasks()
        assert bar.result.suggestions[0].command_text.startswith(expected)

    bar._set_entry("adb start-server")
    bar._refresh()
    app.update_idletasks()
    assert bar.result.mode.value == "related"
    assert all(item.related for item in bar.result.suggestions)
    bar.select_index(1)
    bar.run(SimpleNamespace())
    assert executed == ["adb start-server"]
    assert not bar.suggestions_open

    bar._set_entry("adb reboot b")
    bar._refresh()
    bar._tab()
    assert bar.entry.get() == "adb reboot bootloader"
    assert executed == ["adb start-server"]
    bar._set_entry("adb r")
    bar._refresh()
    app.update_idletasks()
    before_selection = bar.selected_index
    bar._shift_tab()
    assert bar.selected_index != before_selection or len(bar.result.suggestions) == 1
    selected = bar.selected_index
    bar._vertical(None, 1)
    assert bar.selected_index >= selected
    bar._page(None, bar.PAGE_SIZE)
    bar._escape()
    assert not bar.suggestions_open
    bar._manual()
    app.update_idletasks()
    assert bar.suggestions_open and not executed[1:]
    bar.hide_suggestions()

    bar.history.add("adb devices -l")
    bar.history.add("help")
    bar._set_entry("")
    bar._vertical(None, -1)
    assert bar.entry.get() == "help"
    bar._vertical(None, -1)
    assert bar.entry.get() == "adb devices -l"
    assert executed == ["adb start-server"]

    bar._set_entry("adb shell")
    bar.execute_callback = app.execute_command
    bar.run()
    app.update_idletasks()
    assert bar.session_prompt.winfo_ismapped()
    assert not app.interactive_sessions.list()
    bar.hide_session_prompt()
    bar.execute_callback = executed.append
    assert app.command_router.classify("adb devices -l").classification is CommandClassification.ONE_SHOT
    assert app.command_router.classify("mystery command").classification is CommandClassification.AMBIGUOUS
    assert app.command_router.classify("adb '").classification is CommandClassification.UNSUPPORTED

    callbacks = []
    for _index in range(12):
        bar._schedule_refresh()
        callbacks.append(bar.callback_count)
    assert callbacks[-1] == 1 and all(value == 1 for value in callbacks)
    bar._cancel_refresh()

    measurements = []
    for scale in (1.0, 1.25, 1.5):
        ctk.set_widget_scaling(scale)
        for width, height in ((1100, 700), (1200, 760), (1400, 860), (1600, 900)):
            app.geometry(f"{width}x{height}+0+0")
            app.navigate_workspace("Console")
            app.update()
            bar.completion_service = synthetic_service(30, long=True)
            bar._set_entry("adb")
            before = app.console.winfo_height()
            bar._refresh()
            app.update_idletasks()
            entry_bounds = bounds(bar.entry)
            output_bounds = bounds(output)
            dropdown_bounds = bounds(bar.suggestion_panel)
            viewport_before_after = (before, app.console.winfo_height())
            bar.select_index(len(bar.result.suggestions) - 1)
            app.update_idletasks()
            final_bounds = bounds(bar.suggestion_buttons[-1])
            session_bounds = bounds(bar.session_prompt)
            root_bounds = bounds(app)
            assert dropdown_bounds[0] >= bar.winfo_rootx()
            assert dropdown_bounds[0] + dropdown_bounds[2] <= bar.winfo_rootx() + bar.winfo_width()
            assert dropdown_bounds[1] >= entry_bounds[1] + entry_bounds[3]
            assert dropdown_bounds[1] + dropdown_bounds[3] <= (
                root_bounds[1] + root_bounds[3]
            )
            assert app.console.winfo_height() > 40, (
                scale, width, height, root_bounds, entry_bounds,
                dropdown_bounds, app.console.winfo_height()
            )
            assert final_bounds[1] + final_bounds[3] <= (
                bar.suggestion_scroller.canvas.winfo_rooty()
                + bar.suggestion_scroller.canvas.winfo_height() + 2
            )
            assert bar.suggestion_scroller.canvas.xview() == (0.0, 1.0)
            measurements.append(
                (
                    f"{width}x{height}@{int(scale * 100)}%",
                    root_bounds, entry_bounds, output_bounds, dropdown_bounds,
                    len(bar.result.suggestions),
                    final_bounds, viewport_before_after, session_bounds,
                )
            )
            bar.hide_suggestions()
            app.update_idletasks()
            assert not bar.suggestion_panel.winfo_ismapped()
    ctk.set_widget_scaling(1.0)

    bar.completion_service = synthetic_service(1)
    bar._set_entry("adb")
    bar._refresh()
    assert len(bar.result.suggestions) == 1
    bar.accept_index(0)
    assert not executed[1:]

    bar.completion_service = synthetic_service(8)
    bar._set_entry("adb")
    bar._refresh()
    assert len(bar.result.suggestions) == 8
    bar.completion_service = synthetic_service(30)
    bar._set_entry("adb")
    bar._refresh()
    app.update_idletasks()
    output_yview_before_suggestions = output_inner.yview()
    before = bar.suggestion_scroller.canvas.yview()
    bar.suggestion_scroller.router._wheel(
        SimpleNamespace(widget=bar.suggestion_buttons[-1], delta=-120, num=None)
    )
    assert bar.suggestion_scroller.canvas.yview() != before
    assert output_inner.yview() == output_yview_before_suggestions
    suggestion_yview = bar.suggestion_scroller.canvas.yview()
    output.scroll_router._wheel(
        SimpleNamespace(widget=output_inner, delta=120, num=None)
    )
    assert bar.suggestion_scroller.canvas.yview() == suggestion_yview
    assert bar.suggestion_scroller.router._wheel(
        SimpleNamespace(widget=".native.dialog", delta=-120, num=None)
    ) is None

    bar.hide_suggestions()
    bar.completion_service = CommandCompletionService()
    bar._set_entry("adb")
    bar._refresh()
    app.navigate_workspace("Home")
    app.update_idletasks()
    assert not bar.suggestions_open
    app.navigate_workspace("Console")
    app.update_idletasks()
    assert not any(
        str(value).casefold().startswith("blue")
        for value in app.theme.values() if isinstance(value, str)
    )

    latencies = {count: latency(count) for count in (10, 50, 100, 500)}
    binding_count = bar.binding_count
    output_binding_count = output.binding_count
    assert binding_count > 0 and output_binding_count > 0
    bar.close()
    assert bar.callback_count == 0
    assert bar.binding_count == 0
    output.close()
    assert output.binding_count == 0
    assert not any(worker.is_alive() for worker in app._background_workers)
    app.shutdown()
    print(
        "command-assistant-smoke=PASS "
        f"measurements={measurements} contexts={context_results} "
        f"latency_ms={latencies} bindings_before_close={binding_count} "
        f"output_bindings_before_close={output_binding_count} "
        f"output_yview={initial_yview}->{touchpad_yview}->{page_yview} "
        "callbacks_after_close=0 bindings_after_close=0 output_bindings_after_close=0 "
        "readonly-copy-handoff-output-scroll-isolation-streaming-save-clear=PASS "
        "keyboard-history-related-routing-wheel-compact-scaling-shutdown=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
