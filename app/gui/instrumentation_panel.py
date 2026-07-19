"""Responsive instrumentation diagnostics, target discovery, and sessions."""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable, Sequence
from tkinter import messagebox

import customtkinter as ctk

from app.core.command_result import CommandResult
from app.core.device import Device
from app.core.frida_manager import FridaDiagnosis, FridaManager
from app.core.frida_session_manager import FridaSessionManager, FridaSessionReadiness
from app.core.frida_target import FridaTarget, TargetType
from app.core.objection_manager import ObjectionManager
from app.core.target_discovery import TargetDiscovery, TargetDiscoveryResult, filter_targets
from app.core.tool_diagnostics import ToolDiagnostic, ToolDiagnostics
from app.core.worker import BackgroundWorker


class InstrumentationPanel(ctk.CTkScrollableFrame):
    def __init__(
        self,
        parent,
        theme,
        diagnostics: ToolDiagnostics,
        frida: FridaManager,
        objection: ObjectionManager,
        target_discovery: TargetDiscovery,
        frida_sessions: FridaSessionManager,
        log_callback: Callable[[str], None],
    ):
        super().__init__(
            parent, fg_color=theme["bg"], corner_radius=0,
            scrollbar_button_color=theme["gold_dark"],
            scrollbar_button_hover_color=theme["red_hover"],
        )
        self.theme = theme
        self.diagnostics = diagnostics
        self.frida = frida
        self.objection = objection
        self.target_discovery = target_discovery
        self.frida_sessions = frida_sessions
        self.log = log_callback
        self.device: Device | None = None
        self.targets: tuple[FridaTarget, ...] = ()
        self.selected_target: FridaTarget | None = None
        self.target_rows: list[tuple[FridaTarget, ctk.CTkFrame]] = []
        self.frida_preview_command: tuple[str, ...] = ()
        self.objection_preview_command: tuple[str, ...] = ()
        self._last_diagnosis: FridaDiagnosis | None = None
        self._action_buttons: list[ctk.CTkButton] = []
        self._busy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._build_device_section()
        self._build_toolchain_section()
        self._build_frida_section()
        self._build_results_section()
        self._build_target_browser()
        self._build_session_section()
        self._update_target_actions()
        self.refresh_targets_button.configure(state="disabled")

    def _section(self, title: str, row: int, column: int = 0, columnspan: int = 1):
        frame = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["border"], corner_radius=9,
        )
        frame.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            frame, text=title, text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 6))
        return frame

    def _value_row(self, parent, row: int, title: str, initial: str = "Unknown", wrap=430):
        ctk.CTkLabel(
            parent, text=f"{title}:", text_color=self.theme["muted"], anchor="nw",
        ).grid(row=row, column=0, sticky="nw", padx=(12, 6), pady=2)
        label = ctk.CTkLabel(
            parent, text=initial, text_color=self.theme["text"], font=("Consolas", 12),
            anchor="nw", justify="left", wraplength=wrap,
        )
        label.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=2)
        return label

    def _button(self, parent, text: str, command, row: int, column: int, track=True):
        button = ctk.CTkButton(
            parent, text=text, command=command, fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"], text_color=self.theme["text"],
            border_width=1, border_color=self.theme["gold_dark"],
        )
        button.grid(row=row, column=column, sticky="ew", padx=5, pady=4)
        if track:
            self._action_buttons.append(button)
        return button

    def _build_device_section(self):
        frame = self._section("Selected Device", 0, 0)
        self.device_warning = ctk.CTkLabel(
            frame, text="No device selected. Refresh and select an online device.",
            text_color=self.theme["error"], font=("Segoe UI", 13, "bold"), anchor="w",
        )
        self.device_warning.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=3)
        self.device_serial = self._value_row(frame, 2, "Serial", "None")
        self.device_model = self._value_row(frame, 3, "Model")
        self.device_android = self._value_row(frame, 4, "Android")
        self.device_root = self._value_row(frame, 5, "Root")

    def _build_toolchain_section(self):
        frame = self._section("Host Toolchain", 0, 1)
        self.tool_labels = {
            "adb": self._value_row(frame, 1, "ADB", "Not diagnosed"),
            "frida": self._value_row(frame, 2, "Frida", "Not diagnosed"),
            "frida-ps": self._value_row(frame, 3, "frida-ps", "Not diagnosed"),
            "objection": self._value_row(frame, 4, "Objection", "Not diagnosed"),
        }
        self._button(frame, "Diagnose Host", self.diagnose_host, 5, 0).grid(
            columnspan=2, padx=12, pady=(8, 10)
        )

    def _build_frida_section(self):
        frame = self._section("Frida Server", 1, 0, 2)
        self.frida_labels = {
            "path": self._value_row(frame, 1, "Server path", "Not diagnosed"),
            "running": self._value_row(frame, 2, "Server state", "Not diagnosed"),
            "version": self._value_row(frame, 3, "Server version", "Not diagnosed"),
            "match": self._value_row(frame, 4, "Host/server match", "Not diagnosed"),
            "27042": self._value_row(frame, 5, "TCP 27042", "Not diagnosed"),
            "27043": self._value_row(frame, 6, "TCP 27043", "Not diagnosed"),
            "reachable": self._value_row(frame, 7, "Reachability", "Not diagnosed"),
        }
        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=8, column=0, columnspan=2, sticky="ew", padx=7, pady=(6, 8))
        for column in range(4):
            buttons.grid_columnconfigure(column, weight=1)
        actions = (
            ("Diagnose Frida", self.diagnose_frida),
            ("Start Server", lambda: self._lifecycle("Start", self.frida.start_server)),
            ("Stop Server", lambda: self._lifecycle("Stop", self.frida.stop_server)),
            ("Restart Server", lambda: self._lifecycle("Restart", self.frida.restart_server)),
            ("Repair Forwarding", self.repair_forwarding),
            ("List Processes", lambda: self._list_raw(False)),
            ("List Applications", lambda: self._list_raw(True)),
        )
        for index, (text, command) in enumerate(actions):
            self._button(buttons, text, command, index // 4, index % 4)

    def _build_results_section(self):
        frame = self._section("Instrumentation Results", 2, 0, 2)
        self.results = ctk.CTkTextbox(
            frame, height=150, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], font=("Consolas", 12),
            border_width=1, border_color=self.theme["border"], wrap="none",
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.results.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=5)
        self.results.insert("end", "Instrumentation results will appear here.\n")
        ctk.CTkButton(
            frame, text="Clear Results", command=lambda: self.results.delete("1.0", "end"),
            fg_color=self.theme["panel_alt"], hover_color=self.theme["red"],
            text_color=self.theme["text"], border_width=1, border_color=self.theme["gold_dark"],
        ).grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(3, 10))

    def _build_target_browser(self):
        frame = self._section("Target Browser", 3, 0, 2)
        toolbar = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        toolbar.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(
            toolbar, placeholder_text="Search name, identifier, or PID...",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"], placeholder_text_color=self.theme["muted"],
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=4)
        self.search_entry.bind("<KeyRelease>", lambda _event: self._render_targets())
        self.target_type = ctk.CTkSegmentedButton(
            toolbar, values=["All", "Applications", "Processes"],
            command=lambda _value: self._render_targets(),
            selected_color=self.theme["red"], selected_hover_color=self.theme["red_hover"],
            unselected_color=self.theme["panel_alt"],
            unselected_hover_color=self.theme["gold_dark"], text_color=self.theme["text"],
        )
        self.target_type.grid(row=0, column=1, padx=4)
        self.target_type.set("All")
        self.refresh_targets_button = self._button(
            toolbar, "Refresh Targets", self.refresh_targets, 0, 2, track=False
        )
        self._button(toolbar, "Clear Search", self.clear_search, 0, 3)
        self.target_count = ctk.CTkLabel(
            toolbar, text="0 targets", text_color=self.theme["gold"],
            font=("Segoe UI", 12, "bold"),
        )
        self.target_count.grid(row=0, column=4, padx=8)

        self.target_list = ctk.CTkScrollableFrame(
            frame, height=250, fg_color=self.theme["terminal_bg"],
            border_width=1, border_color=self.theme["border"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.target_list.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=12, pady=6)
        self.target_list.grid_columnconfigure(0, weight=1)

        details = ctk.CTkFrame(frame, fg_color=self.theme["panel_alt"], corner_radius=7)
        details.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 10))
        details.grid_columnconfigure(1, weight=1)
        self.target_detail_labels = {
            "name": self._value_row(details, 0, "Name", "None", 650),
            "identifier": self._value_row(details, 1, "Identifier", "None", 650),
            "pid": self._value_row(details, 2, "PID", "None"),
            "type": self._value_row(details, 3, "Type", "None"),
            "running": self._value_row(details, 4, "Running", "No"),
        }
        self.version_warning = ctk.CTkLabel(
            details, text="", text_color=self.theme["error"],
            font=("Segoe UI", 12, "bold"), justify="left", anchor="w", wraplength=750,
        )
        self.version_warning.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(3, 8))
        self.copy_guidance_button = ctk.CTkButton(
            details, text="Copy Version Guidance", command=self.copy_version_guidance,
            fg_color=self.theme["panel_alt"], hover_color=self.theme["red"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"], state="disabled",
        )
        self.copy_guidance_button.grid(row=6, column=0, columnspan=2, sticky="e", padx=12, pady=(0, 8))

    def _build_session_section(self):
        frame = self._section("Live Session Launcher", 4, 0, 2)
        options = ctk.CTkFrame(frame, fg_color="transparent")
        options.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        options.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(options, text="Trace pattern:", text_color=self.theme["muted"]).grid(
            row=0, column=0, padx=4
        )
        self.trace_pattern = ctk.CTkEntry(
            options, placeholder_text="Optional function pattern, e.g. open*",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"], placeholder_text_color=self.theme["muted"],
        )
        self.trace_pattern.grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkLabel(options, text="Objection transport:", text_color=self.theme["muted"]).grid(
            row=0, column=2, padx=4
        )
        self.transport = ctk.CTkSegmentedButton(
            options, values=["Socket", "USB"], command=lambda _value: self.preview_objection(),
            selected_color=self.theme["red"], selected_hover_color=self.theme["red_hover"],
            unselected_color=self.theme["panel_alt"],
            unselected_hover_color=self.theme["gold_dark"], text_color=self.theme["text"],
        )
        self.transport.grid(row=0, column=3, padx=4)
        self.transport.set("Socket")

        frida_buttons = ctk.CTkFrame(frame, fg_color="transparent")
        frida_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", padx=7)
        for column in range(6):
            frida_buttons.grid_columnconfigure(column, weight=1)
        self.frida_preview_button = self._button(
            frida_buttons, "Preview Frida Command", self.preview_frida, 0, 0
        )
        self.frida_attach_button = self._button(frida_buttons, "Attach", lambda: self.launch_frida("attach"), 0, 1)
        self.frida_spawn_button = self._button(frida_buttons, "Spawn", lambda: self.launch_frida("spawn"), 0, 2)
        self.frida_pid_button = self._button(frida_buttons, "Attach by PID", lambda: self.launch_frida("pid"), 0, 3)
        self.frida_trace_button = self._button(frida_buttons, "Trace", lambda: self.launch_frida("trace"), 0, 4)
        self.frida_copy_button = self._button(
            frida_buttons, "Copy Command", lambda: self.copy_preview("frida"), 0, 5
        )

        objection_buttons = ctk.CTkFrame(frame, fg_color="transparent")
        objection_buttons.grid(row=3, column=0, columnspan=2, sticky="ew", padx=7)
        for column in range(5):
            objection_buttons.grid_columnconfigure(column, weight=1)
        self.objection_preview_button = self._button(
            objection_buttons, "Preview Objection Command", self.preview_objection, 0, 0
        )
        self.objection_validate_button = self._button(
            objection_buttons, "Validate", self.validate_objection, 0, 1
        )
        self.objection_attach_button = self._button(
            objection_buttons, "Attach", lambda: self.launch_objection(False), 0, 2
        )
        self.objection_spawn_button = self._button(
            objection_buttons, "Spawn", lambda: self.launch_objection(True), 0, 3
        )
        self.objection_copy_button = self._button(
            objection_buttons, "Copy Command", lambda: self.copy_preview("objection"), 0, 4
        )

        self.command_preview = ctk.CTkTextbox(
            frame, height=76, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], font=("Consolas", 12),
            border_width=1, border_color=self.theme["gold_dark"], wrap="word",
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.command_preview.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 10))
        self.command_preview.configure(state="disabled")

    def set_selected_device(self, device: Device | None):
        previous_serial = self.device.serial if self.device else None
        self.device = device
        current_serial = device.serial if device else None
        if previous_serial != current_serial or (device is not None and not device.connected):
            self.clear_targets("Device selection changed; target data cleared.")
        if device is None:
            self.device_warning.configure(text="No device selected. Refresh and select an online device.")
            values = ("None", "Unknown", "Unknown", "Unknown")
        else:
            self.device_warning.configure(text="" if device.connected else f"Warning: device state is {device.state}.")
            values = (device.serial, device.display_name, device.android_version, self._state(device.root))
        for label, value in zip(
            (self.device_serial, self.device_model, self.device_android, self.device_root), values
        ):
            label.configure(text=value)
        self.refresh_targets_button.configure(state="normal" if device and device.connected else "disabled")

    def diagnose_host(self):
        self._run_operation("Host diagnostics", self.diagnostics.diagnose_all, self._show_host_diagnostics)

    def _show_host_diagnostics(self, tools: dict[str, ToolDiagnostic]):
        lines = []
        for name, label in self.tool_labels.items():
            tool = tools[name]
            details = tool.executable_path or "Missing"
            if tool.version:
                details += f" — {tool.version}"
            label.configure(text=details, text_color=self.theme["success"] if tool.installed else self.theme["error"])
            lines.append(f"{tool.display_name}: {details}")
            if tool.error:
                self.log(f"[HOST TOOL ERROR] {tool.display_name}: {tool.error}")
        self._append_results("Host diagnostics", "\n".join(lines))

    def diagnose_frida(self):
        serial = self._serial()
        self._run_operation("Frida diagnostics", lambda: self.frida.diagnose(serial), self._show_frida_diagnosis)

    def _show_frida_diagnosis(self, diagnosis: FridaDiagnosis):
        self._last_diagnosis = diagnosis
        values = {
            "path": diagnosis.server_path or "Not found",
            "running": "Running" if diagnosis.server_running else "Stopped",
            "version": diagnosis.server_version or "Unknown",
            "match": self._state(diagnosis.versions_match),
            "27042": self._state(diagnosis.port_27042),
            "27043": self._state(diagnosis.port_27043),
            "reachable": self._state(diagnosis.reachable),
        }
        for name, value in values.items():
            self.frida_labels[name].configure(text=value)
        self.device_root.configure(text=self._state(diagnosis.root_available))
        output = list(diagnosis.recommendations)
        if diagnosis.errors:
            output.extend(("", "Errors:", *diagnosis.errors))
        self._append_results("Frida diagnosis", "\n".join(output))
        self._update_mismatch_warning()
        for error in diagnosis.errors:
            self.log(f"[FRIDA ERROR] {error}")

    def _lifecycle(self, action: str, operation):
        serial = self._serial()
        self._run_operation(
            f"{action} Frida server", lambda: operation(serial),
            lambda value: self._complete_stale_operation(value, "Frida server state changed"),
        )

    def repair_forwarding(self):
        serial = self._serial()
        self._run_operation(
            "Repair Frida forwarding", lambda: self.frida.repair_forwarding(serial),
            lambda value: self._complete_stale_operation(value, "Frida forwarding changed"),
        )

    def _complete_stale_operation(self, value, reason):
        self._show_command_results(value)
        self.clear_targets(f"{reason}; refresh targets.")

    def _list_raw(self, applications: bool):
        serial = self._serial()
        operation = self.frida.list_applications if applications else self.frida.list_processes
        title = "Raw Frida applications" if applications else "Raw Frida processes"
        self._run_operation(title, lambda: operation(serial), lambda result: self._show_listing(title, result))

    def _show_listing(self, title: str, result: CommandResult):
        self._append_results(title, result.output or "No output.")

    def refresh_targets(self):
        serial = self._serial()
        self.refresh_targets_button.configure(state="disabled")
        self._run_operation(
            "Target discovery", lambda: self.target_discovery.discover_combined(serial),
            self._apply_discovery,
        )

    def _apply_discovery(self, result: TargetDiscoveryResult):
        self.refresh_targets_button.configure(state="normal" if self.device else "disabled")
        if result.serial != self._serial():
            self._report_failure("Target discovery", "Selected device changed before discovery completed.")
            return
        self.targets = result.targets
        self.selected_target = None
        self._render_targets()
        self._show_selected_target()
        message = f"Discovered {len(result.targets)} structured target(s)."
        self._append_results("Target discovery", message)
        if result.errors:
            self._report_failure("Target discovery", "; ".join(result.errors))

    def clear_search(self):
        self.search_entry.delete(0, "end")
        self.target_type.set("All")
        self._render_targets()

    def clear_targets(self, reason: str | None = None):
        self.targets = ()
        self.selected_target = None
        self.frida_preview_command = ()
        self.objection_preview_command = ()
        self._render_targets()
        self._show_selected_target()
        self._render_previews()
        if reason:
            self._append_results("Targets stale", reason)

    def _render_targets(self):
        for widget in self.target_list.winfo_children():
            widget.destroy()
        self.target_rows.clear()
        visible = filter_targets(self.targets, self.search_entry.get(), self.target_type.get())
        if self.selected_target is not None and self.selected_target not in visible:
            self.selected_target = None
            self._show_selected_target()
        self.target_count.configure(text=f"{len(visible)} target{'s' if len(visible) != 1 else ''}")
        if not visible:
            ctk.CTkLabel(
                self.target_list, text="No matching targets. Refresh or adjust the filter.",
                text_color=self.theme["muted"],
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=18)
            return
        for row_index, target in enumerate(visible):
            row = ctk.CTkFrame(
                self.target_list, fg_color=self.theme["panel_alt"], corner_radius=7,
                border_width=1, border_color=self.theme["border"],
            )
            row.grid(row=row_index, column=0, sticky="ew", padx=3, pady=3)
            row.grid_columnconfigure(0, weight=1)
            title = ctk.CTkLabel(
                row, text=target.name or target.identifier or "Unnamed target",
                text_color=self.theme["gold"], font=("Segoe UI", 13, "bold"),
                anchor="w", justify="left", wraplength=650,
            )
            title.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 1))
            details = ctk.CTkLabel(
                row,
                text=(
                    f"Identifier: {target.identifier or '—'}    PID: {target.pid or '—'}\n"
                    f"Type: {target.target_type.value.title()}    "
                    f"Running: {'Yes' if target.running else 'No'}"
                ),
                text_color=self.theme["text"], font=("Consolas", 11),
                anchor="w", justify="left", wraplength=700,
            )
            details.grid(row=1, column=0, sticky="ew", padx=10, pady=(1, 7))
            for widget in (row, title, details):
                widget.bind("<Button-1>", lambda _event, item=target: self.select_target(item))
            self.target_rows.append((target, row))
        self._highlight_selected_row()

    def select_target(self, target: FridaTarget):
        self.selected_target = target
        self._highlight_selected_row()
        self._show_selected_target()
        self.preview_frida()
        self.preview_objection()

    def _highlight_selected_row(self):
        for target, row in self.target_rows:
            selected = target == self.selected_target
            row.configure(
                fg_color=self.theme["red"] if selected else self.theme["panel_alt"],
                border_color=self.theme["gold"] if selected else self.theme["border"],
                border_width=2 if selected else 1,
            )
            if selected:
                self.after_idle(lambda widget=row: self.target_list._parent_canvas.yview_moveto(
                    max(0.0, widget.winfo_y() / max(1, self.target_list.winfo_reqheight()))
                ))

    def _show_selected_target(self):
        target = self.selected_target
        values = {
            "name": target.name if target else "None",
            "identifier": target.identifier if target and target.identifier else "None",
            "pid": str(target.pid) if target and target.pid is not None else "None",
            "type": target.target_type.value.title() if target else "None",
            "running": self._state(target.running) if target else "No",
        }
        for name, value in values.items():
            self.target_detail_labels[name].configure(text=value)
        self._update_mismatch_warning()
        self._update_target_actions()

    def _update_mismatch_warning(self):
        diagnosis = self._last_diagnosis
        warning = ""
        if diagnosis and diagnosis.versions_match is False:
            warning = self.frida_sessions.version_mismatch_warning(
                diagnosis.host_version, diagnosis.server_version
            )
        self.version_warning.configure(text=warning)
        self.copy_guidance_button.configure(state="normal" if warning else "disabled")

    def copy_version_guidance(self):
        guidance = self.version_warning.cget("text")
        if not guidance:
            return
        self.clipboard_clear()
        self.clipboard_append(guidance)
        self.log("[FRIDA] Version-mismatch guidance copied to clipboard.")

    def _update_target_actions(self):
        if not hasattr(self, "frida_attach_button"):
            return
        target = self.selected_target
        general = "normal" if target and not self._busy else "disabled"
        spawn = "normal" if target and target.application_identifier and not self._busy else "disabled"
        pid = "normal" if target and target.pid is not None and not self._busy else "disabled"
        for button in (self.frida_attach_button, self.frida_trace_button, self.objection_attach_button):
            button.configure(state=general)
        for button in (
            self.frida_preview_button, self.objection_preview_button,
            self.objection_validate_button,
        ):
            button.configure(state=general)
        for button in (self.frida_spawn_button, self.objection_spawn_button):
            button.configure(state=spawn)
        self.frida_pid_button.configure(state=pid)
        self.frida_copy_button.configure(
            state="normal" if self.frida_preview_command and not self._busy else "disabled"
        )
        self.objection_copy_button.configure(
            state="normal" if self.objection_preview_command and not self._busy else "disabled"
        )

    def preview_frida(self, mode="attach"):
        try:
            if mode == "spawn":
                command = self.frida_sessions.build_spawn_command(self.selected_target)
            elif mode == "pid":
                command = self.frida_sessions.build_pid_command(self.selected_target)
            elif mode == "trace":
                command = self.frida_sessions.build_trace_command(
                    self.selected_target, self.trace_pattern.get()
                )
            else:
                command = self.frida_sessions.build_attach_command(self.selected_target)
        except ValueError as exc:
            self._report_failure("Frida preview", str(exc))
            return
        self._set_preview(command, "frida")

    def launch_frida(self, mode: str):
        try:
            if mode == "spawn":
                command = self.frida_sessions.build_spawn_command(self.selected_target)
            elif mode == "pid":
                command = self.frida_sessions.build_pid_command(self.selected_target)
            elif mode == "trace":
                command = self.frida_sessions.build_trace_command(self.selected_target, self.trace_pattern.get())
            else:
                command = self.frida_sessions.build_attach_command(self.selected_target)
        except ValueError as exc:
            self._report_failure("Frida session", str(exc))
            return
        self._set_preview(command, "frida")
        serial = self._serial()
        self._run_operation(
            "Frida session readiness",
            lambda: self.frida_sessions.readiness(
                serial, self.selected_target, require_pid=mode == "pid",
                require_application=mode == "spawn", trace=mode == "trace",
            ),
            lambda readiness: self._launch_frida_if_ready(readiness, command),
        )

    def _launch_frida_if_ready(self, readiness: FridaSessionReadiness, command: Sequence[str]):
        if not readiness.ready:
            self._report_failure("Frida session", "; ".join(readiness.errors))
            return
        if not self._confirm_warning(readiness.warning):
            self.log("[FRIDA] Session launch cancelled after version warning.")
            return
        self._run_operation(
            "Launch external Frida session", lambda: self.frida_sessions.launch(command),
            self._show_command_results,
        )

    def preview_objection(self):
        target = self._objection_target()
        try:
            command = self.objection.build_attach_command(target, self.transport.get(), self._serial())
        except ValueError as exc:
            if self.selected_target is not None:
                self._report_failure("Objection preview", str(exc))
            return
        self._set_preview(command, "objection")

    def validate_objection(self):
        serial, target, transport = self._serial(), self._objection_target(), self.transport.get()
        self._run_operation(
            "Objection validation", lambda: self.objection.readiness(serial, target, transport),
            lambda readiness: self._append_results(
                "Objection validation", "Ready." if readiness.ready else "\n".join(readiness.errors)
            ),
        )

    def launch_objection(self, spawn: bool):
        serial, target, transport = self._serial(), self._objection_target(), self.transport.get()
        try:
            builder = self.objection.build_spawn_command if spawn else self.objection.build_attach_command
            command = builder(target, transport, serial)
        except ValueError as exc:
            self._report_failure("Objection session", str(exc))
            return
        self._set_preview(command, "objection")

        def readiness():
            frida_ready = self.frida_sessions.readiness(
                serial, self.selected_target, require_application=spawn
            )
            objection_ready = self.objection.readiness(serial, target, transport)
            return frida_ready, objection_ready

        self._run_operation(
            "Objection session readiness", readiness,
            lambda value: self._launch_objection_if_ready(value, command),
        )

    def _launch_objection_if_ready(self, value, command):
        frida_ready, objection_ready = value
        errors = frida_ready.errors + objection_ready.errors
        if errors:
            self._report_failure("Objection session", "; ".join(dict.fromkeys(errors)))
            return
        if not self._confirm_warning(frida_ready.warning):
            self.log("[OBJECTION] Session launch cancelled after version warning.")
            return
        self._run_operation(
            "Launch external Objection session",
            lambda: self.objection.launch_external_session(command), self._show_command_results,
        )

    def _confirm_warning(self, warning: str | None) -> bool:
        if not warning:
            return True
        self.version_warning.configure(text=warning)
        self.copy_guidance_button.configure(state="normal")
        self._append_results("Frida version warning", warning)
        return messagebox.askyesno(
            "Frida Version Mismatch",
            f"{warning}\n\nContinue with the external interactive session?",
            parent=self.winfo_toplevel(),
        )

    def copy_preview(self, kind: str):
        command = (
            self.frida_preview_command if kind == "frida"
            else self.objection_preview_command
        )
        if not command:
            self._report_failure("Copy command", "Preview a command first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._preview_text(command))
        self.log(f"[INSTRUMENTATION] {kind.title()} command copied to clipboard.")

    def _set_preview(self, command: Sequence[str], kind: str):
        if kind == "frida":
            self.frida_preview_command = tuple(command)
        else:
            self.objection_preview_command = tuple(command)
        self._render_previews()

    def _render_previews(self):
        lines = []
        if self.frida_preview_command:
            lines.append(f"Frida: {self._preview_text(self.frida_preview_command)}")
        if self.objection_preview_command:
            lines.append(f"Objection: {self._preview_text(self.objection_preview_command)}")
        self.command_preview.configure(state="normal")
        self.command_preview.delete("1.0", "end")
        self.command_preview.insert("1.0", "\n".join(lines))
        self.command_preview.configure(state="disabled")
        self._update_target_actions()

    @staticmethod
    def _preview_text(command: Sequence[str]) -> str:
        return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)

    def _objection_target(self) -> str:
        target = self.selected_target
        return (target.identifier or target.name) if target else ""

    def _run_operation(self, title: str, target, callback):
        if self._busy:
            self.log("[BUSY] An instrumentation operation is already running.")
            return
        self._set_busy(True)
        self.log(f"[INSTRUMENTATION] {title}...")

        def guarded():
            try:
                return True, target()
            except Exception as exc:
                return False, exc

        BackgroundWorker(
            guarded,
            callback=lambda outcome: self.after(0, self._finish_operation, title, outcome, callback),
        ).start()

    def _finish_operation(self, title: str, outcome, callback):
        self._set_busy(False)
        success, value = outcome
        if not success:
            self._report_failure(title, str(value))
            return
        callback(value)
        failures = self._result_failures(value)
        if failures:
            self._report_failure(title, "; ".join(failures))
        else:
            self.log(f"[INSTRUMENTATION] {title} complete.")

    def _show_command_results(self, value):
        results = value if isinstance(value, tuple) else (value,)
        text = "\n".join(
            result.output or "Complete." for result in results if isinstance(result, CommandResult)
        )
        self._append_results("Operation", text)

    @staticmethod
    def _result_failures(value) -> list[str]:
        results = value if isinstance(value, tuple) else (value,)
        failures = [
            result.output or "Command failed." for result in results
            if isinstance(result, CommandResult) and not result.ok
        ]
        if hasattr(value, "ready") and not value.ready:
            failures.extend(value.errors)
        return failures

    def _report_failure(self, title: str, error: str):
        message = error or "Operation failed."
        self._append_results(f"{title} failed", message)
        self.log(f"[INSTRUMENTATION ERROR] {title}: {message}")

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in self._action_buttons:
            button.configure(state=state)
        if hasattr(self, "refresh_targets_button"):
            self.refresh_targets_button.configure(
                state="disabled" if busy or not (self.device and self.device.connected) else "normal"
            )
        self._update_target_actions()

    def _append_results(self, title: str, text: str):
        self.results.insert("end", f"\n=== {title} ===\n{text}\n")
        self.results.see("end")

    def _serial(self) -> str | None:
        return self.device.serial if self.device else None

    @staticmethod
    def _state(value: bool | None) -> str:
        if value is None:
            return "Unknown"
        return "Yes" if value else "No"
