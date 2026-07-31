"""Host-owned live Logcat Investigator workspace."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from app.gui.read_only_text import ReadOnlyTextView
from app.modules.logcat import (
    LogcatCaptureState,
    LogcatFilter,
    LogcatPriority,
)


class LogcatInvestigatorPanel(ctk.CTkFrame):
    """Bounded transcript presentation with no raw manager or process exposure."""

    PRIORITY_LABELS = tuple(priority.label for priority in LogcatPriority)
    REQUIRED_CAPABILITIES = frozenset(("read-selected-device", "read-device-logs"))

    def __init__(
        self,
        parent,
        theme,
        capture_service,
        *,
        ui_dispatch,
        start_background,
    ):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme = theme
        self.capture_service = capture_service
        self.ui_dispatch = ui_dispatch
        self.start_background = start_background
        self.closed = False
        self.context = None
        self.selected_device = {}
        self.approved_capabilities = frozenset()
        self.last_snapshot = capture_service.snapshot()
        self._displayed_sequences: list[int] = []
        self._display_filter_generation = -1
        self._busy = False
        self._filter_trace_ids = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_status()
        self._build_controls()
        self._build_filters()
        self.transcript = ReadOnlyTextView(
            self,
            fg_color=theme["terminal_bg"],
            text_color=theme["terminal_text"],
            border_color=theme["border"],
            border_width=1,
            font=theme["terminal_font"],
            wrap="none",
        )
        self.transcript.grid(
            row=3, column=0, sticky="nsew", padx=8, pady=(4, 4)
        )
        self.footer = ctk.CTkLabel(
            self,
            text=(
                "Capture has not started. Device logs may contain identifiers, "
                "paths, messages, tokens, account information, and application data."
            ),
            text_color=theme["muted"],
            anchor="w",
            justify="left",
            wraplength=560,
        )
        self.footer.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.subscription = capture_service.subscribe(self._snapshot_changed)

    def _build_status(self):
        strip = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["gold_dark"],
        )
        strip.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 3))
        strip.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            strip,
            text="Selected: None · Bound: None · State: idle · Buffered: 0 · Visible: 0 · Dropped: 0",
            text_color=self.theme["gold"],
            anchor="w",
            justify="left",
            wraplength=650,
            font=("Segoe UI", 9, "bold"),
        )
        self.status.grid(row=0, column=0, sticky="ew", padx=10, pady=7)
        self.device_warning = ctk.CTkLabel(
            strip,
            text="",
            text_color=self.theme["error"],
            anchor="w",
            justify="left",
            wraplength=650,
        )
        self.device_warning.grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 4)
        )

    def _button(self, parent, text, command, column, *, primary=False):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=self.theme["red"] if primary else self.theme["panel_alt"],
            hover_color=(
                self.theme["red_hover"] if primary else self.theme["gold_dark"]
            ),
            text_color=self.theme["text"],
            border_width=1,
            border_color=self.theme["gold_dark"],
            width=88,
        )
        button.grid(row=0, column=column, padx=4, pady=7)
        return button

    def _build_controls(self):
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=8)
        controls.grid_columnconfigure(4, weight=1)
        self.start_button = self._button(
            controls, "Start Capture", self.start_capture, 0, primary=True
        )
        self.pause_button = self._button(
            controls, "Pause View", self.toggle_pause, 1
        )
        self.stop_button = self._button(controls, "Stop", self.stop_capture, 2)
        self.clear_button = self._button(
            controls, "Clear View", self.clear_view, 3
        )
        ctk.CTkLabel(
            controls,
            text="Clear View: host memory only.",
            text_color=self.theme["muted"],
            anchor="e",
        ).grid(row=0, column=4, sticky="e", padx=5)

    def _entry(self, parent, placeholder, column, width=150):
        entry = ctk.CTkEntry(
            parent,
            placeholder_text=placeholder,
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
            width=width,
        )
        entry.grid(row=0, column=column, sticky="ew", padx=4, pady=7)
        return entry

    def _build_filters(self):
        filters = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
        )
        filters.grid(row=2, column=0, sticky="ew", padx=8, pady=3)
        filters.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(
            filters, text="Filters:", text_color=self.theme["gold"]
        ).grid(row=0, column=0, padx=(9, 3))
        self.priority = ctk.CTkComboBox(
            filters,
            values=list(self.PRIORITY_LABELS),
            state="readonly",
            command=lambda _value: self.apply_filters(),
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            button_color=self.theme["red"],
            button_hover_color=self.theme["red_hover"],
            dropdown_fg_color=self.theme["panel_alt"],
            dropdown_hover_color=self.theme["red"],
            text_color=self.theme["text"],
            dropdown_text_color=self.theme["text"],
            width=82,
        )
        self.priority.grid(row=0, column=1, padx=4, pady=7)
        self.priority.set("Verbose")
        self.tag_filter = self._entry(filters, "Tag contains", 2, 90)
        self.pid_filter = self._entry(filters, "Exact PID", 3, 70)
        self.message_filter = self._entry(
            filters, "Message contains", 4, 120
        )
        self.reset_button = self._button(
            filters, "Reset Filters", self.reset_filters, 5
        )
        for entry in (self.tag_filter, self.pid_filter, self.message_filter):
            entry.bind("<Return>", lambda _event: self.apply_filters(), add="+")

    def apply_context(self, context):
        if self.closed:
            return
        self.context = context
        self.selected_device = dict(getattr(context, "selected_device", {}) or {})
        self.approved_capabilities = frozenset(
            getattr(context, "approved_capabilities", ())
        )
        selected_serial = str(self.selected_device.get("serial", ""))
        self.capture_service.set_selected_serial(selected_serial)
        self._refresh_controls(self.last_snapshot)

    def _suitable_serial(self):
        if self.selected_device.get("state") != "device":
            return ""
        return str(self.selected_device.get("serial", ""))

    def _authorized(self):
        return self.REQUIRED_CAPABILITIES <= self.approved_capabilities

    def _run(self, operation, pending_text):
        if self.closed or self._busy:
            return False
        self._busy = True
        self.footer.configure(text=pending_text, text_color=self.theme["gold"])
        self._refresh_controls(self.last_snapshot)

        def finished(result):
            if self.closed:
                return
            self._busy = False
            if not result.ok:
                self.footer.configure(
                    text=result.error or "Logcat operation failed.",
                    text_color=self.theme["error"],
                )
            self._refresh_controls(result.snapshot)

        self.start_background(operation, lambda result: self.ui_dispatch(finished, result))
        return True

    def start_capture(self):
        serial = self._suitable_serial()
        if not serial:
            self.footer.configure(
                text="Select an online ADB device before starting capture.",
                text_color=self.theme["error"],
            )
            return False
        if not self._authorized():
            self.footer.configure(
                text=(
                    "Approved read-selected-device and read-device-logs "
                    "capabilities are required."
                ),
                text_color=self.theme["error"],
            )
            return False
        return self._run(
            lambda: self.capture_service.start(serial),
            f"Starting bounded capture for {serial}…",
        )

    def toggle_pause(self):
        state = self.last_snapshot.state
        if state is LogcatCaptureState.RUNNING:
            result = self.capture_service.pause_view()
        elif state is LogcatCaptureState.VIEW_PAUSED:
            result = self.capture_service.resume_view()
        else:
            return False
        if not result.ok:
            self.footer.configure(text=result.error, text_color=self.theme["error"])
        return result.ok

    def stop_capture(self):
        return self._run(
            self.capture_service.stop,
            "Stopping the owned Logcat process…",
        )

    def clear_view(self):
        self._displayed_sequences.clear()
        self.transcript.clear()
        self.capture_service.clear()
        return True

    def apply_filters(self):
        raw_pid = self.pid_filter.get().strip()
        if raw_pid and not raw_pid.isdecimal():
            self.footer.configure(
                text="PID filter must be an exact non-negative integer.",
                text_color=self.theme["error"],
            )
            return False
        value = LogcatFilter(
            LogcatPriority.from_value(self.priority.get()),
            self.tag_filter.get(),
            int(raw_pid) if raw_pid else None,
            self.message_filter.get(),
        )
        self.start_background(
            lambda: self.capture_service.set_filter(value),
            lambda _snapshot: None,
        )
        return True

    def reset_filters(self):
        self.priority.set("Verbose")
        for entry in (self.tag_filter, self.pid_filter, self.message_filter):
            entry.delete(0, "end")
        self.start_background(
            lambda: self.capture_service.set_filter(LogcatFilter()),
            lambda _snapshot: None,
        )
        return True

    def _snapshot_changed(self, snapshot):
        if self.closed:
            return
        previous_state = self.last_snapshot.state
        self.last_snapshot = snapshot
        self._refresh_controls(snapshot)
        if snapshot.state is LogcatCaptureState.VIEW_PAUSED:
            return
        force = (
            previous_state is LogcatCaptureState.VIEW_PAUSED
            or snapshot.filter_generation != self._display_filter_generation
        )
        self._render_transcript(snapshot.visible_records, force=force)
        self._display_filter_generation = snapshot.filter_generation

    def _render_transcript(self, records, *, force=False):
        sequences = [record.sequence for record in records]
        if force or not self._displayed_sequences or not sequences:
            self.transcript.replace(
                "\n".join(record.display_line() for record in records)
                + ("\n" if records else "")
            )
            self._displayed_sequences = sequences
            if records:
                self.transcript._textbox.see("end")
            return
        old = self._displayed_sequences
        overlap = next(
            (index for index, sequence in enumerate(old) if sequence == sequences[0]),
            None,
        )
        if overlap is None or old[overlap:] != sequences[: len(old) - overlap]:
            self.transcript.replace(
                "\n".join(record.display_line() for record in records) + "\n"
            )
        else:
            if overlap:
                self.transcript.delete("1.0", f"{overlap + 1}.0")
            existing = len(old) - overlap
            additions = records[existing:]
            if additions:
                self.transcript.append(
                    "\n".join(record.display_line() for record in additions) + "\n"
                )
        self._displayed_sequences = sequences
        if records:
            self.transcript._textbox.see("end")

    def _refresh_controls(self, snapshot):
        selected = str(self.selected_device.get("serial", "")) or "None"
        bound = snapshot.capture_serial or "None"
        self.status.configure(
            text=(
                f"Selected: {selected} · Bound: {bound} · "
                f"State: {snapshot.state.value} · Buffered: {snapshot.buffered_count} · "
                f"Visible: {snapshot.visible_count} · Dropped: {snapshot.dropped_records}"
            )
        )
        changed = (
            bool(snapshot.capture_serial)
            and selected != "None"
            and selected != snapshot.capture_serial
            and snapshot.state in self.capture_service.ACTIVE
        )
        self.device_warning.configure(
            text=(
                f"Selection changed; capture remains bound to {snapshot.capture_serial}."
                if changed
                else ""
            )
        )
        if changed:
            self.device_warning.grid()
        else:
            self.device_warning.grid_remove()
        can_start = (
            not self._busy
            and bool(self._suitable_serial())
            and self._authorized()
            and snapshot.state not in self.capture_service.ACTIVE
        )
        self.start_button.configure(state="normal" if can_start else "disabled")
        can_pause = (
            not self._busy
            and snapshot.state
            in {LogcatCaptureState.RUNNING, LogcatCaptureState.VIEW_PAUSED}
        )
        self.pause_button.configure(
            state="normal" if can_pause else "disabled",
            text=(
                "Resume View"
                if snapshot.state is LogcatCaptureState.VIEW_PAUSED
                else "Pause View"
            ),
        )
        can_stop = (
            not self._busy
            and snapshot.state
            in {
                LogcatCaptureState.STARTING,
                LogcatCaptureState.RUNNING,
                LogcatCaptureState.VIEW_PAUSED,
                LogcatCaptureState.FAILED,
                LogcatCaptureState.STOPPING,
            }
        )
        self.stop_button.configure(state="normal" if can_stop else "disabled")
        self.clear_button.configure(state="disabled" if self._busy else "normal")
        if snapshot.state is LogcatCaptureState.VIEW_PAUSED:
            text = "View paused; capture continues in memory."
            color = self.theme["gold"]
        elif snapshot.error_text:
            text = snapshot.error_text
            color = self.theme["error"]
        else:
            text = (
                f"{snapshot.status_text} Privacy: device logs may contain "
                "identifiers, paths, messages, tokens, account information, "
                "and application data."
            )
            color = self.theme["muted"]
        self.footer.configure(text=text, text_color=color)

    def can_change_device(self, _serial):
        return True

    def cleanup(self):
        if self.closed:
            return
        self.closed = True
        if self.subscription is not None:
            self.subscription.cancel()
            self.subscription = None
        self.transcript.close()
        self._displayed_sequences.clear()
        if self.capture_service.process_count or self.capture_service.worker_count:
            self.start_background(
                self.capture_service.close,
                lambda _result: None,
            )
        else:
            self.capture_service.close()
