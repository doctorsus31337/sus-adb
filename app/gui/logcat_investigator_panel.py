"""Host-owned live Logcat Investigator workspace."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from app.gui.read_only_text import ReadOnlyTextView
from app.gui.customtkinter_compat import ScopedEventBindings
from app.modules.logcat import (
    LogcatAnalysisFilter,
    LogcatCaptureState,
    LogcatEventKind,
    LogcatEventSeverity,
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
        self.analysis_service = capture_service.analysis_service
        self.ui_dispatch = ui_dispatch
        self.start_background = start_background
        self.closed = False
        self.context = None
        self.selected_device = {}
        self.approved_capabilities = frozenset()
        self.last_snapshot = capture_service.snapshot()
        self.last_analysis_snapshot = self.analysis_service.snapshot()
        self._displayed_sequences: list[int] = []
        self._display_filter_generation = -1
        self._analysis_filter_generation = -1
        self._busy = False
        self._filter_trace_ids = []
        self.view_mode = "Transcript"
        self.events_page = None
        self.event_timeline = None
        self.event_details = None
        self.event_stack = None
        self.event_context = None
        self.selected_event_id = ""
        self._compact_event_details = False
        self._context_focus_event_id = ""
        self.bindings = ScopedEventBindings()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_status()
        self._build_controls()
        self._build_view_switch()
        self._build_filters()
        self.content_host = ctk.CTkFrame(self, fg_color="transparent")
        self.content_host.grid(row=3, column=0, sticky="nsew", padx=8, pady=(4, 4))
        self.content_host.grid_rowconfigure(0, weight=1)
        self.content_host.grid_columnconfigure(0, weight=1)
        self.transcript_page = ctk.CTkFrame(
            self.content_host, fg_color="transparent"
        )
        self.transcript_page.grid(row=0, column=0, sticky="nsew")
        self.transcript_page.grid_rowconfigure(0, weight=1)
        self.transcript_page.grid_columnconfigure(0, weight=1)
        self.transcript = ReadOnlyTextView(
            self.transcript_page,
            fg_color=theme["terminal_bg"],
            text_color=theme["terminal_text"],
            border_color=theme["border"],
            border_width=1,
            font=theme["terminal_font"],
            wrap="none",
        )
        self.transcript.grid(
            row=0, column=0, sticky="nsew"
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
        self.bindings.bind(self, "<Configure>", self._panel_configured)
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
        self.controls = controls
        controls.grid(row=1, column=0, sticky="ew", padx=8)
        controls.grid_columnconfigure(7, weight=1)
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

    def _build_view_switch(self):
        self.transcript_view_button = self._button(
            self.controls, "Transcript", self.show_transcript, 4, primary=True
        )
        self.events_view_button = self._button(
            self.controls, "Events", self.show_events, 5
        )
        self.return_live_button = self._button(
            self.controls, "Return to Live View", self.return_to_live_view, 6
        )
        self.return_live_button.grid_remove()
        self.view_guidance = ctk.CTkLabel(
            self.controls,
            text="Clear affects bounded host memory only.",
            text_color=self.theme["muted"],
            anchor="e",
        )
        self.view_guidance.grid(row=0, column=7, sticky="e", padx=5)

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
        self.transcript_filters = filters
        for entry in (self.tag_filter, self.pid_filter, self.message_filter):
            entry.bind("<Return>", lambda _event: self.apply_filters(), add="+")

    def _analysis_combo(self, parent, values, column, width):
        combo = ctk.CTkComboBox(
            parent,
            values=list(values),
            state="readonly",
            command=lambda _value: self.apply_analysis_filters(),
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            button_color=self.theme["red"],
            button_hover_color=self.theme["red_hover"],
            dropdown_fg_color=self.theme["panel_alt"],
            dropdown_hover_color=self.theme["red"],
            text_color=self.theme["text"],
            dropdown_text_color=self.theme["text"],
            width=width,
        )
        combo.grid(row=0, column=column, padx=4, pady=7)
        return combo

    def _build_events_view(self):
        if self.events_page is not None:
            return
        from app.gui.logcat_event_timeline import LogcatEventTimeline

        filters = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
        )
        filters.grid_columnconfigure(4, weight=1)
        self.event_filter_label = ctk.CTkLabel(
            filters, text="Event filters:", text_color=self.theme["gold"]
        )
        self.event_filter_label.grid(row=0, column=0, padx=(9, 3))
        self.event_kind_filter = self._analysis_combo(
            filters,
            ("All", *(value.label for value in LogcatEventKind)),
            1,
            132,
        )
        self.event_kind_filter.set("All")
        self.event_severity_filter = self._analysis_combo(
            filters,
            tuple(value.label for value in LogcatEventSeverity),
            2,
            104,
        )
        self.event_severity_filter.set(LogcatEventSeverity.INFORMATION.label)
        self.event_process_filter = self._entry(
            filters, "Process/package contains", 3, 150
        )
        self.event_text_filter = self._entry(filters, "Search events", 4, 160)
        self.reset_analysis_button = self._button(
            filters, "Reset Analysis Filters", self.reset_analysis_filters, 5
        )
        for entry in (self.event_process_filter, self.event_text_filter):
            entry.bind(
                "<Return>", lambda _event: self.apply_analysis_filters(), add="+"
            )
        self.event_filters = filters

        page = ctk.CTkFrame(self.content_host, fg_color="transparent")
        page.grid_rowconfigure(1, weight=1)
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        self.event_counts = ctk.CTkLabel(
            page,
            text="Unique: 0 · Visible: 0 · Occurrences: 0 · Dropped groups: 0",
            text_color=self.theme["gold"],
            anchor="w",
            justify="left",
        )
        self.event_counts.grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=2, pady=(0, 4)
        )
        self.event_timeline = LogcatEventTimeline(
            page,
            self.theme,
            details_callback=self.view_event_details,
            transcript_callback=self.show_in_transcript,
        )
        self.event_timeline.grid(
            row=1, column=0, sticky="nsew", padx=(0, 4), pady=(0, 2)
        )
        self.event_details_frame = ctk.CTkFrame(
            page,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
        )
        self.event_details_frame.grid_rowconfigure(1, weight=1)
        self.event_details_frame.grid_rowconfigure(3, weight=1)
        self.event_details_frame.grid_rowconfigure(5, weight=2)
        self.event_details_frame.grid_columnconfigure(0, weight=1)
        self.event_details_title = ctk.CTkLabel(
            self.event_details_frame,
            text="Event Details",
            text_color=self.theme["gold"],
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self.event_details_title.grid(
            row=0, column=0, sticky="ew", padx=8, pady=(7, 3)
        )
        common = {
            "fg_color": self.theme["terminal_bg"],
            "text_color": self.theme["terminal_text"],
            "border_color": self.theme["border"],
            "border_width": 1,
            "font": self.theme["terminal_font"],
            "wrap": "word",
        }
        self.event_details = ReadOnlyTextView(
            self.event_details_frame,
            initial_text="Select an event to inspect its bounded local details.",
            **common,
        )
        self.event_details.grid(row=1, column=0, sticky="nsew", padx=8)
        ctk.CTkLabel(
            self.event_details_frame,
            text="Reconstructed Stack",
            text_color=self.theme["muted"],
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=8, pady=(5, 2))
        self.event_stack = ReadOnlyTextView(
            self.event_details_frame,
            initial_text="No reconstructed stack for the selected event.",
            **common,
        )
        self.event_stack.grid(row=3, column=0, sticky="nsew", padx=8)
        ctk.CTkLabel(
            self.event_details_frame,
            text="Bounded Raw Context",
            text_color=self.theme["muted"],
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=8, pady=(5, 2))
        self.event_context = ReadOnlyTextView(
            self.event_details_frame,
            initial_text="No contextual records selected.",
            **common,
        )
        self.event_context.grid(
            row=5, column=0, sticky="nsew", padx=8, pady=(0, 5)
        )
        actions = ctk.CTkFrame(self.event_details_frame, fg_color="transparent")
        actions.grid(row=6, column=0, sticky="ew", padx=4, pady=(0, 4))
        self.details_transcript_button = self._button(
            actions,
            "Show in Transcript",
            self._show_selected_in_transcript,
            0,
        )
        self.back_events_button = self._button(
            actions, "Back to Events", self._show_event_list, 1
        )
        self.event_details_frame.grid(
            row=1, column=1, sticky="nsew", padx=(4, 0), pady=(0, 2)
        )
        self.events_page = page
        self._layout_events()
        self._refresh_event_view(self.analysis_service.snapshot())

    def _panel_configured(self, _event=None):
        if self.winfo_width() < 1_180:
            self.view_guidance.grid_remove()
        else:
            self.view_guidance.grid()
        if self.events_page is not None:
            self._layout_events()

    def _layout_events(self):
        if self.events_page is None:
            return
        wide = self.winfo_width() >= 1_100
        self._layout_event_filters(wide)
        self.event_timeline.grid_forget()
        self.event_details_frame.grid_forget()
        if wide:
            self.event_counts.grid()
            self._compact_event_details = False
            self.back_events_button.grid_remove()
            self.events_page.grid_rowconfigure(1, weight=1)
            self.events_page.grid_rowconfigure(2, weight=0)
            self.events_page.grid_columnconfigure(0, weight=3)
            self.events_page.grid_columnconfigure(1, weight=2)
            self.event_timeline.grid(
                row=1, column=0, sticky="nsew", padx=(0, 4), pady=(0, 2)
            )
            self.event_details_frame.grid(
                row=1, column=1, sticky="nsew", padx=(4, 0), pady=(0, 2)
            )
        else:
            self.event_counts.grid_remove()
            self.events_page.grid_rowconfigure(1, weight=1)
            self.events_page.grid_rowconfigure(2, weight=0)
            self.events_page.grid_columnconfigure(0, weight=1)
            self.events_page.grid_columnconfigure(1, weight=0)
            if self._compact_event_details:
                self.back_events_button.grid()
                self.event_details_frame.grid(
                    row=1, column=0, sticky="nsew", pady=(0, 2)
                )
            else:
                self.back_events_button.grid_remove()
                self.event_timeline.grid(
                    row=1, column=0, sticky="nsew", pady=(0, 2)
                )

    def _layout_event_filters(self, wide):
        if wide:
            placements = (
                (self.event_filter_label, 0),
                (self.event_kind_filter, 1),
                (self.event_severity_filter, 2),
                (self.event_process_filter, 3),
                (self.event_text_filter, 4),
                (self.reset_analysis_button, 5),
            )
            for widget, column in placements:
                widget.grid_configure(row=0, column=column, pady=7)
        else:
            for widget, row, column in (
                (self.event_filter_label, 0, 0),
                (self.event_kind_filter, 0, 1),
                (self.event_severity_filter, 0, 2),
                (self.event_process_filter, 1, 0),
                (self.event_text_filter, 1, 1),
                (self.reset_analysis_button, 1, 2),
            ):
                widget.grid_configure(row=row, column=column, pady=2)

    def _show_event_list(self):
        self._compact_event_details = False
        self._layout_events()
        return True

    def show_transcript(self):
        self.view_mode = "Transcript"
        if self.events_page is not None:
            self.events_page.grid_remove()
            self.event_filters.grid_remove()
        self.transcript_page.grid()
        self.transcript_filters.grid()
        self.transcript_view_button.configure(fg_color=self.theme["red"])
        self.events_view_button.configure(fg_color=self.theme["panel_alt"])
        if not self._context_focus_event_id:
            self._render_transcript(self.last_snapshot.visible_records, force=True)
            self._refresh_controls(self.last_snapshot)
        return True

    def show_events(self):
        self._build_events_view()
        self.view_mode = "Events"
        self.transcript_page.grid_remove()
        self.transcript_filters.grid_remove()
        self.events_page.grid(row=0, column=0, sticky="nsew")
        self.event_filters.grid(row=2, column=0, sticky="ew", padx=8, pady=3)
        self.transcript_view_button.configure(fg_color=self.theme["panel_alt"])
        self.events_view_button.configure(fg_color=self.theme["red"])
        self._refresh_event_view(self.analysis_service.snapshot())
        self._refresh_controls(self.last_snapshot)
        return True

    def apply_analysis_filters(self):
        kind_label = self.event_kind_filter.get()
        kind = next(
            (
                value for value in LogcatEventKind
                if value.label == kind_label
            ),
            None,
        )
        severity = next(
            value for value in LogcatEventSeverity
            if value.label == self.event_severity_filter.get()
        )
        snapshot = self.analysis_service.set_filter(
            LogcatAnalysisFilter(
                kind,
                severity,
                self.event_process_filter.get(),
                self.event_text_filter.get(),
            )
        )
        self._refresh_event_view(snapshot)
        return True

    def reset_analysis_filters(self):
        self.event_kind_filter.set("All")
        self.event_severity_filter.set(LogcatEventSeverity.INFORMATION.label)
        for entry in (self.event_process_filter, self.event_text_filter):
            entry.delete(0, "end")
        self._refresh_event_view(self.analysis_service.reset_filters())
        return True

    def _refresh_event_view(self, snapshot):
        self.last_analysis_snapshot = snapshot
        if self.events_page is None:
            return
        self.event_counts.configure(
            text=(
                f"Unique: {snapshot.unique_event_count} · "
                f"Visible: {snapshot.visible_event_count} · "
                f"Occurrences: {snapshot.total_occurrence_count} · "
                f"Dropped groups: {snapshot.dropped_event_groups}"
            )
        )
        self.event_timeline.set_events(tuple(reversed(snapshot.visible_events)))
        selected = next(
            (
                value for value in snapshot.events
                if value.event_id == self.selected_event_id
            ),
            None,
        )
        if selected is not None:
            self.view_event_details(selected, activate=False)
        elif not snapshot.events:
            self.selected_event_id = ""
            self.event_details.replace(
                "No analyzed events are retained. Capture continues only when "
                "explicitly started."
            )
            self.event_stack.replace(
                "No reconstructed stack for the selected event."
            )
            self.event_context.replace("No contextual records selected.")

    def view_event_details(self, event, *, activate=True):
        self.selected_event_id = event.event_id
        if activate and self.winfo_width() < 1_100:
            self._compact_event_details = True
            self._layout_events()
        if self.event_timeline is not None:
            self.event_timeline.select_event(event.event_id)
        self.event_details_title.configure(text=event.title)
        self.event_details.replace(
            "\n".join(
                (
                    f"Event ID: {event.event_id}",
                    f"Fingerprint: {event.fingerprint}",
                    f"Detector/rule: {event.detector_id}",
                    f"Kind: {event.kind.label}",
                    f"Severity: {event.severity.label}",
                    f"Confidence: {event.confidence.label}",
                    f"Process/package: {event.process or event.package or 'Unavailable'}",
                    f"PID/TID: {event.pid if event.pid is not None else 'Unavailable'}"
                    f" / {event.tid if event.tid is not None else 'Unavailable'}",
                    f"Sequences: {event.first_sequence} → {event.last_sequence}",
                    f"First/latest: {event.first_timestamp_text or 'Unavailable'}"
                    f" → {event.last_timestamp_text or 'Unavailable'}",
                    f"Occurrences: {event.occurrence_count}",
                    "",
                    event.summary,
                    "",
                    "Privacy: device logs may contain identifiers, paths, messages, "
                    "tokens, account information, and application data. Details "
                    "remain local and are not persisted.",
                )
            )
        )
        self.event_stack.replace(
            "\n".join(event.stack_lines)
            if event.stack_lines
            else "No reconstructed stack for this event kind."
        )
        self.event_context.replace(
            "\n".join(record.display_line() for record in event.context_records)
            if event.context_records
            else "No contextual records remain for this event."
        )
        return True

    def _show_selected_in_transcript(self):
        event = next(
            (
                value for value in self.last_analysis_snapshot.events
                if value.event_id == self.selected_event_id
            ),
            None,
        )
        return self.show_in_transcript(event) if event is not None else False

    def show_in_transcript(self, event):
        records = tuple(
            record for record in self.last_snapshot.records
            if event.context_first_sequence
            <= record.sequence
            <= event.context_last_sequence
        )
        available = {record.sequence for record in self.last_snapshot.records}
        relevant_present = bool(event.relevant_record_sequences) and all(
            value in available for value in event.relevant_record_sequences
        )
        self.show_transcript()
        if not records or not relevant_present:
            self._context_focus_event_id = ""
            self.return_live_button.grid_remove()
            self.footer.configure(
                text="Context is no longer present in the bounded Logcat buffer.",
                text_color=self.theme["error"],
            )
            return False
        self._context_focus_event_id = event.event_id
        self.return_live_button.grid()
        body = (
            f"===== EVENT CONTEXT START · {event.event_id} =====\n"
            + "\n".join(record.display_line() for record in records)
            + f"\n===== EVENT CONTEXT END · {event.event_id} =====\n"
        )
        self.transcript.replace(body)
        self._displayed_sequences = [record.sequence for record in records]
        self.transcript._textbox.see("1.0")
        self.footer.configure(
            text=(
                "Showing a bounded event context without changing transcript "
                "filters. Use Return to Live View to resume the normal filtered view."
            ),
            text_color=self.theme["gold"],
        )
        return True

    def return_to_live_view(self):
        self._context_focus_event_id = ""
        self.return_live_button.grid_remove()
        self._render_transcript(self.last_snapshot.visible_records, force=True)
        self._refresh_controls(self.last_snapshot)
        return True

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
        self._context_focus_event_id = ""
        self.return_live_button.grid_remove()
        self._displayed_sequences.clear()
        self.transcript.clear()
        self.capture_service.clear()
        self.selected_event_id = ""
        self._refresh_event_view(self.analysis_service.snapshot())
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
        analysis_snapshot = self.analysis_service.snapshot()
        self._refresh_event_view(analysis_snapshot)
        self._refresh_controls(snapshot)
        if self._context_focus_event_id:
            return
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
        analysis_counts = (
            f"Unique {self.last_analysis_snapshot.unique_event_count} · "
            f"Visible {self.last_analysis_snapshot.visible_event_count} · "
            f"Occurrences {self.last_analysis_snapshot.total_occurrence_count} · "
            f"Dropped groups {self.last_analysis_snapshot.dropped_event_groups}."
        )
        if snapshot.state is LogcatCaptureState.VIEW_PAUSED:
            text = "View paused; capture and analysis continue in memory."
            if self.view_mode == "Events":
                text += f" {analysis_counts}"
            color = self.theme["gold"]
        elif snapshot.error_text:
            text = snapshot.error_text
            color = self.theme["error"]
        else:
            text = f"{snapshot.status_text} "
            if self.view_mode == "Events":
                text += f"{analysis_counts} "
            text += (
                "Privacy: device logs may contain identifiers, paths, messages, "
                "tokens, account information, and application data."
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
        self.bindings.close()
        if self.event_timeline is not None:
            self.event_timeline.close()
        for view in (self.event_details, self.event_stack, self.event_context):
            if view is not None:
                view.close()
        self.transcript.close()
        self._displayed_sequences.clear()
        if self.capture_service.process_count or self.capture_service.worker_count:
            self.start_background(
                self.capture_service.close,
                lambda _result: None,
            )
        else:
            self.capture_service.close()
