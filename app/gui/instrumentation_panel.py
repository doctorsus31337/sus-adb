"""Responsive Frida and Objection control center."""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable

import customtkinter as ctk

from app.core.command_result import CommandResult
from app.core.device import Device
from app.core.frida_manager import FridaDiagnosis, FridaManager
from app.core.objection_manager import ObjectionManager
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
        log_callback: Callable[[str], None],
    ):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme = theme
        self.diagnostics = diagnostics
        self.frida = frida
        self.objection = objection
        self.log = log_callback
        self.device: Device | None = None
        self._action_buttons: list[ctk.CTkButton] = []
        self._busy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._build_device_section()
        self._build_toolchain_section()
        self._build_frida_section()
        self._build_results_section()
        self._build_objection_section()
        self._update_command_preview()

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

    def _value_row(self, parent, row: int, title: str, initial: str = "Unknown"):
        ctk.CTkLabel(
            parent, text=f"{title}:", text_color=self.theme["muted"], anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=(12, 6), pady=2)
        label = ctk.CTkLabel(
            parent, text=initial, text_color=self.theme["text"],
            font=("Consolas", 12), anchor="w", wraplength=430,
        )
        label.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=2)
        return label

    def _button(self, parent, text: str, command, row: int, column: int):
        button = ctk.CTkButton(
            parent, text=text, command=command, fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"], text_color=self.theme["text"],
            border_width=1, border_color=self.theme["gold_dark"],
        )
        button.grid(row=row, column=column, sticky="ew", padx=5, pady=4)
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
        self._button(frame, "Diagnose Host", self.diagnose_host, 5, 0).grid(columnspan=2, padx=12, pady=(8, 10))

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
            ("List Processes", lambda: self._list_frida(False)),
            ("List Applications", lambda: self._list_frida(True)),
        )
        for index, (text, command) in enumerate(actions):
            self._button(buttons, text, command, index // 4, index % 4)

    def _build_results_section(self):
        frame = self._section("Frida Results", 2, 0, 2)
        frame.grid_rowconfigure(1, weight=1)
        self.results = ctk.CTkTextbox(
            frame, height=180, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], font=("Consolas", 12),
            border_width=1, border_color=self.theme["border"], wrap="none",
        )
        self.results.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=5)
        self.results.insert("end", "Instrumentation results will appear here.\n")
        ctk.CTkButton(
            frame, text="Clear Results", command=lambda: self.results.delete("1.0", "end"),
            fg_color=self.theme["panel_alt"], hover_color=self.theme["red"],
            text_color=self.theme["text"], border_width=1, border_color=self.theme["gold_dark"],
        ).grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(3, 10))

    def _build_objection_section(self):
        frame = self._section("Objection Launcher", 3, 0, 2)
        ctk.CTkLabel(frame, text="Target:", text_color=self.theme["muted"]).grid(
            row=1, column=0, sticky="w", padx=12, pady=4
        )
        self.target_entry = ctk.CTkComboBox(
            frame, values=[], fg_color=self.theme["terminal_bg"],
            button_color=self.theme["red"], button_hover_color=self.theme["red_hover"],
            border_color=self.theme["gold_dark"], text_color=self.theme["text"],
            command=lambda _value: self._update_command_preview(),
        )
        self.target_entry.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=4)
        self.target_entry.bind("<KeyRelease>", lambda _event: self._update_command_preview())
        ctk.CTkLabel(frame, text="Transport:", text_color=self.theme["muted"]).grid(
            row=2, column=0, sticky="w", padx=12, pady=4
        )
        self.transport = ctk.CTkSegmentedButton(
            frame, values=["Socket", "USB"], command=lambda _value: self._update_command_preview(),
            selected_color=self.theme["red"], selected_hover_color=self.theme["red_hover"],
            unselected_color=self.theme["panel_alt"],
            unselected_hover_color=self.theme["gold_dark"], text_color=self.theme["text"],
        )
        self.transport.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=4)
        self.transport.set("Socket")
        self.command_preview = self._value_row(frame, 3, "Command preview", "")
        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", padx=7, pady=(6, 10))
        for column in range(4):
            buttons.grid_columnconfigure(column, weight=1)
        self._button(buttons, "Validate", self.validate_objection, 0, 0)
        self._button(buttons, "Copy Command", self.copy_command, 0, 1)
        self._button(buttons, "Attach", lambda: self.launch_objection(False), 0, 2)
        self._button(buttons, "Spawn", lambda: self.launch_objection(True), 0, 3)

    def set_selected_device(self, device: Device | None):
        self.device = device
        if device is None:
            self.device_warning.configure(text="No device selected. Refresh and select an online device.")
            self.device_serial.configure(text="None")
            self.device_model.configure(text="Unknown")
            self.device_android.configure(text="Unknown")
            self.device_root.configure(text="Unknown")
        else:
            self.device_warning.configure(
                text="" if device.connected else f"Warning: device state is {device.state}."
            )
            self.device_serial.configure(text=device.serial)
            self.device_model.configure(text=device.display_name)
            self.device_android.configure(text=device.android_version)
            self.device_root.configure(text=self._state(device.root))
        self._update_command_preview()

    def diagnose_host(self):
        self._run_operation("Host diagnostics", self.diagnostics.diagnose_all, self._show_host_diagnostics)

    def _show_host_diagnostics(self, tools: dict[str, ToolDiagnostic]):
        lines = []
        for name, label in self.tool_labels.items():
            tool = tools[name]
            if tool.installed:
                details = tool.executable_path or "Installed"
                if tool.version:
                    details += f" — {tool.version}"
            else:
                details = "Missing"
            label.configure(text=details, text_color=self.theme["success"] if tool.installed else self.theme["error"])
            lines.append(f"{tool.display_name}: {details}")
            if tool.error:
                self.log(f"[HOST TOOL ERROR] {tool.display_name}: {tool.error}")
        self._append_results("Host diagnostics", "\n".join(lines))

    def diagnose_frida(self):
        serial = self._serial()
        self._run_operation("Frida diagnostics", lambda: self.frida.diagnose(serial), self._show_frida_diagnosis)

    def _show_frida_diagnosis(self, diagnosis: FridaDiagnosis):
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
        for error in diagnosis.errors:
            self.log(f"[FRIDA ERROR] {error}")

    def _lifecycle(self, action: str, operation):
        serial = self._serial()
        self._run_operation(f"{action} Frida server", lambda: operation(serial), self._show_command_results)

    def repair_forwarding(self):
        serial = self._serial()
        self._run_operation(
            "Repair Frida forwarding", lambda: self.frida.repair_forwarding(serial),
            self._show_command_results,
        )

    def _list_frida(self, applications: bool):
        serial = self._serial()
        operation = self.frida.list_applications if applications else self.frida.list_processes
        title = "Frida applications" if applications else "Frida processes"
        self._run_operation(title, lambda: operation(serial), lambda result: self._show_listing(title, result))

    def _show_listing(self, title: str, result: CommandResult):
        self._append_results(title, result.output or "No output.")
        if result.ok:
            targets = self._extract_targets(result.stdout)
            if targets:
                self.target_entry.configure(values=targets)

    def validate_objection(self):
        serial, target, transport = self._objection_values()
        self._run_operation(
            "Objection validation",
            lambda: self.objection.readiness(serial, target, transport),
            self._show_objection_readiness,
        )

    def _show_objection_readiness(self, readiness):
        text = "Ready." if readiness.ready else "\n".join(readiness.errors)
        self._append_results("Objection validation", text)
        if not readiness.ready:
            self.log(f"[OBJECTION ERROR] {text.replace(chr(10), '; ')}")

    def copy_command(self):
        preview = self.command_preview.cget("text")
        if not preview:
            self._report_failure("Copy command", "Enter a valid target first.")
            return
        self.clipboard_clear()
        self.clipboard_append(preview)
        self.log("[OBJECTION] Command copied to clipboard.")

    def launch_objection(self, spawn: bool):
        serial, target, transport = self._objection_values()
        action = "spawn" if spawn else "attach"

        def operation():
            readiness = self.objection.readiness(serial, target, transport)
            if not readiness.ready:
                return CommandResult.from_command(("objection",), -1, error="; ".join(readiness.errors))
            builder = self.objection.build_spawn_command if spawn else self.objection.build_attach_command
            return self.objection.launch_external_session(builder(target, transport, serial))

        self._run_operation(f"Objection {action}", operation, self._show_command_results)

    def _update_command_preview(self):
        try:
            serial, target, transport = self._objection_values()
            command = self.objection.build_attach_command(target, transport, serial)
            preview = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
        except ValueError:
            preview = ""
        self.command_preview.configure(text=preview)

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
        text = "\n".join(result.output or "Complete." for result in results if isinstance(result, CommandResult))
        self._append_results("Operation", text)

    @staticmethod
    def _result_failures(value) -> list[str]:
        results = value if isinstance(value, tuple) else (value,)
        failures = [
            result.output or "Command failed."
            for result in results
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

    def _append_results(self, title: str, text: str):
        self.results.insert("end", f"\n=== {title} ===\n{text}\n")
        self.results.see("end")

    def _serial(self) -> str | None:
        return self.device.serial if self.device else None

    def _objection_values(self):
        return self._serial(), self.target_entry.get().strip(), self.transport.get().casefold()

    @staticmethod
    def _state(value: bool | None) -> str:
        if value is None:
            return "Unknown"
        return "Yes" if value else "No"

    @staticmethod
    def _extract_targets(output: str) -> list[str]:
        targets: list[str] = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                targets.append(parts[-1])
        return list(dict.fromkeys(targets))
