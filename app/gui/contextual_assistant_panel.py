"""Host-owned panels for capability-safe Frida and Objection assistants."""

from __future__ import annotations

import queue
from tkinter import messagebox

import customtkinter as ctk

from app.core.contextual_assistant import ContextualAssistantService
from app.core.worker import BackgroundWorker
from app.widgets.responsive_action_grid import (
    HorizontalNavigationStrip,
    ResponsiveActionGrid,
)


class ContextualAssistantPanel(ctk.CTkFrame):
    FRIDA_SECTIONS = (
        "Overview", "Device Readiness", "Installed Applications",
        "Runtime Targets", "Sessions", "Script Studio", "Script Launcher",
        "Troubleshooting", "Command Reference", "Learn",
    )
    OBJECTION_SECTIONS = (
        "Overview", "Device & Target", "Connection Plan", "Sessions",
        "Command Search", "Command Builder", "Troubleshooting", "History",
        "Reference", "Learn",
    )

    def __init__(
        self,
        parent,
        theme,
        service: ContextualAssistantService,
        kind,
        *,
        refresh_devices,
        open_guided_setup,
        open_sessions,
        open_script_studio,
        open_learning,
        open_help,
        ui_dispatch=None,
        confirm=None,
    ):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme = theme
        self.service = service
        self.kind = kind
        self.refresh_devices = refresh_devices
        self.open_guided_setup = open_guided_setup
        self.open_sessions = open_sessions
        self.open_script_studio = open_script_studio
        self.open_learning = open_learning
        self.open_help = open_help
        self.confirm = confirm or (
            lambda title, text: messagebox.askyesno(
                title, text, parent=self.winfo_toplevel()
            )
        )
        self.context = None
        self.state = self.service.state(kind, None)
        self.last_plan = None
        self.selected_script = ""
        self._workers = set()
        self._closed = False
        self._queue = None
        self._poll_id = None
        if ui_dispatch is None:
            self._queue = queue.Queue()
            self.dispatch = lambda callback, *args: self._queue.put((callback, args))
        else:
            self.dispatch = ui_dispatch
        self.sections = (
            self.FRIDA_SECTIONS if kind == "frida" else self.OBJECTION_SECTIONS
        )
        self.current_section = self.sections[0]
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_navigation()
        self._build_content()
        self.show_section(self.current_section)
        if self._queue is not None:
            self._poll_id = self.after(20, self._poll)

    @property
    def title_text(self):
        return "FRIDA ASSISTANT" if self.kind == "frida" else "OBJECTION ASSISTANT"

    def _build_header(self):
        header = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text=self.title_text, text_color=self.theme["gold"],
            font=("Times New Roman", 24, "bold"), anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 3))
        ctk.CTkButton(
            header, text="Help", width=90,
            command=lambda: self.open_help(f"{self.kind}-assistant"),
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"],
        ).grid(row=0, column=1, padx=10, pady=(7, 3))
        self.summary = ctk.CTkLabel(
            header, text="", text_color=self.theme["text"], anchor="w",
            justify="left", wraplength=1100,
        )
        self.summary.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
        self.recommendation = ctk.CTkLabel(
            header, text="", text_color=self.theme["gold"], anchor="w",
            justify="left", wraplength=1100,
        )
        self.recommendation.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 7)
        )

    def _build_navigation(self):
        self.navigation = HorizontalNavigationStrip(
            self, self.theme,
            tuple(
                (name, lambda value=name: self.show_section(value))
                for name in self.sections
            ),
        )
        self.navigation.grid(row=1, column=0, sticky="ew", padx=6, pady=2)

    def _build_content(self):
        self.content = ctk.CTkScrollableFrame(
            self, fg_color=self.theme["panel"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.content.grid(row=2, column=0, sticky="nsew", padx=6, pady=(2, 6))
        self.content.grid_columnconfigure(0, weight=1)
        self.section_title = ctk.CTkLabel(
            self.content, text="", text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w",
        )
        self.section_title.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 3))
        self.status = ctk.CTkLabel(
            self.content, text="", text_color=self.theme["muted"],
            anchor="w", justify="left", wraplength=1050,
        )
        self.status.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self.actions = ResponsiveActionGrid(
            self.content, self.theme, (), minimum_width=145
        )
        self.actions.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        self.output = ctk.CTkTextbox(
            self.content, height=260, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], border_width=1,
            border_color=self.theme["border"], wrap="word",
        )
        self.output.grid(row=3, column=0, sticky="nsew", padx=10, pady=7)
        self.output.configure(state="disabled")

    def _replace_actions(self, items):
        self.actions.destroy()
        self.actions = ResponsiveActionGrid(
            self.content, self.theme, items, minimum_width=145
        )
        self.actions.grid(row=2, column=0, sticky="ew", padx=8, pady=4)

    def _section_actions(self, section):
        common = (
            ("Refresh Device State", self.refresh_devices),
            ("Help", lambda: self.open_help(f"{self.kind}-assistant")),
        )
        if section == "Overview":
            return common + (
                ("Guided Instrumentation Setup", self.open_guided_setup),
                ("Learn", lambda: self.open_learning(
                    "frida-foundations" if self.kind == "frida" else "objection-foundations"
                )),
            )
        if section in {"Device Readiness", "Device & Target"}:
            name = "frida" if self.kind == "frida" else "objection"
            return common + (
                (f"Check Host {name.title()}", lambda: self._run(
                    lambda: self.service.check_tool(name)
                )),
                ("Diagnose Frida Route", lambda: self._run(
                    lambda: self.service.diagnose_frida(self.state)
                )),
            )
        if section == "Installed Applications":
            return common + (("Scan Installed Applications", lambda: self._run(
                lambda: self.service.scan_installed(self.state)
            )),)
        if section == "Runtime Targets":
            return common + (("Scan Runtime Targets", lambda: self._run(
                lambda: self.service.scan_runtime(self.state)
            )),)
        if section in {"Sessions", "Connection Plan"}:
            if self.kind == "frida":
                return (
                    ("Open Frida REPL", lambda: self.open_sessions("Frida REPL")),
                    ("Open Frida Trace", lambda: self.open_sessions("Frida Trace")),
                    ("Preview Attach", lambda: self.preview_frida("attach")),
                    ("Preview Spawn", lambda: self.preview_frida("spawn")),
                )
            return (
                ("Open Sessions Center", lambda: self.open_sessions("Objection")),
                ("Preview Attach", lambda: self.preview_objection(False)),
                ("Preview Spawn", lambda: self.preview_objection(True)),
                ("Start Confirmed Session", self.launch_last_plan),
            )
        if section in {"Script Studio", "Script Launcher"}:
            return (
                ("Open Script Studio", self.open_script_studio),
                ("Select Script Studio Script", self.select_script),
                ("Copy Script Path", lambda: self.copy_text(self.selected_script)),
                ("Preview Frida Command", lambda: self.preview_frida("attach")),
                ("Copy Frida Command", self.copy_plan),
                ("Open Frida REPL", lambda: self.open_sessions("Frida REPL")),
            )
        if section in {"Troubleshooting", "Command Search"}:
            return (
                ("Connection-loss Guidance", lambda: self.show_operation(
                    self.service.troubleshoot(self.kind, "")
                )),
                ("Open Session Recovery", lambda: self.open_sessions(
                    "Active Sessions" if self.kind == "objection" else "Frida REPL"
                )),
            )
        if section == "History":
            return (("Refresh Local History", self.show_history),)
        if section in {"Learn"}:
            return (
                ("Open Learning Center", lambda: self.open_learning(
                    "frida-foundations" if self.kind == "frida" else "objection-foundations"
                )),
                ("Help", lambda: self.open_help(f"{self.kind}-assistant")),
            )
        return (
            ("Preview Attach", lambda: (
                self.preview_frida("attach") if self.kind == "frida"
                else self.preview_objection(False)
            )),
            ("Copy Command", self.copy_plan),
            ("Help", lambda: self.open_help(f"{self.kind}-assistant")),
        )

    def show_section(self, section):
        if section not in self.sections:
            return
        self.current_section = section
        self.navigation.set_active(section)
        self.section_title.configure(text=section)
        self._replace_actions(self._section_actions(section))
        descriptions = {
            "Overview": "Current state and the safest useful next step. Opening this assistant never scans, attaches, spawns, or loads a script.",
            "Command Search": "Search and explain local reference material. No Objection command is issued.",
            "Command Builder": "Build copyable attach or spawn previews using the selected serial and target.",
            "Command Reference": "Preview commands for handoff to dedicated sessions; the one-shot Console is not used.",
            "Reference": "`help android sslpinning` displays help and is not itself the SSL-pinning action.",
            "Learn": "Educational lessons are secondary, local-only, and synthetic by default.",
        }
        self.status.configure(
            text=descriptions.get(
                section,
                "Use an explicit action below. Results remain bound to the selected serial and target.",
            )
        )

    def apply_context(self, context):
        self.context = context
        self.state = self.service.state(self.kind, context)
        target = self.state.target or "None"
        pid = (
            f" · PID {self.state.pid}"
            if self.state.interface_mode == "advanced" and self.state.pid else ""
        )
        self.summary.configure(
            text=(
                f"Device: {self.state.device} · Serial: {self.state.serial or 'None'} · "
                f"ADB: {self.state.adb_state} · Target: {target}{pid} · "
                f"Endpoint: {self.state.endpoint} · Mode: {self.state.interface_mode.title()}"
            )
        )
        self.recommendation.configure(
            text=f"Recommended next step: {self.state.recommended_next_step}"
        )

    def _run(self, operation):
        self.status.configure(text="Working…", text_color=self.theme["gold"])
        worker = BackgroundWorker(
            operation,
            lambda result: self.dispatch(self._finish_worker, worker, result),
        )
        self._workers.add(worker)
        worker.start()

    def _finish_worker(self, worker, result):
        self._workers.discard(worker)
        if not self._closed:
            self.show_operation(result)

    def show_operation(self, operation):
        self.status.configure(
            text=operation.title,
            text_color=self.theme["success"] if operation.ok else self.theme["error"],
        )
        self._set_output(operation.detail)

    def preview_frida(self, mode):
        self.last_plan = self.service.frida_plan(
            self.state, mode=mode, script_path=self.selected_script
        )
        self._set_output(
            self.last_plan.preview() + (
                "\n\n" + "\n".join(self.last_plan.errors)
                if self.last_plan.errors else ""
            )
        )

    def preview_objection(self, spawn):
        self.last_plan = self.service.objection_plan(self.state, spawn=spawn)
        self._set_output(
            self.last_plan.preview() + (
                "\n\n" + "\n".join(self.last_plan.errors)
                if self.last_plan.errors else ""
            )
        )

    def select_script(self):
        operation = self.service.scripts()
        descriptors = tuple(operation.value or ())
        if descriptors:
            self.selected_script = descriptors[0].path
            operation = type(operation)(
                True, operation.title,
                f"{operation.detail}\nSelected: {descriptors[0].name}\n"
                f"Library path: {descriptors[0].path}",
                descriptors,
            )
        self.show_operation(operation)

    def launch_last_plan(self):
        if self.last_plan is None:
            self.preview_objection(False)
            return
        if not self.last_plan.ready:
            self._set_output("\n".join(self.last_plan.errors))
            return
        if not self.confirm(
            "Launch External Objection Session",
            "Launch this exact preview in the configured external terminal?\n\n"
            + self.last_plan.preview(),
        ):
            return
        self._run(lambda: self.service.launch(self.last_plan))

    def show_history(self):
        values = self.service.objection_history()
        self._set_output(
            "\n".join(values) if values else "No preserved local Objection command history."
        )

    def copy_plan(self):
        self.copy_text(self.last_plan.preview() if self.last_plan else "")

    def copy_text(self, value):
        if not value:
            self.status.configure(
                text="Nothing is available to copy.", text_color=self.theme["error"]
            )
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        self.status.configure(text="Copied.", text_color=self.theme["success"])

    def _set_output(self, value):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", value or "")
        self.output.configure(state="disabled")

    def _poll(self):
        if self._closed or self._queue is None:
            return
        while True:
            try:
                callback, args = self._queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self._poll_id = self.after(20, self._poll)

    def cleanup(self):
        self._closed = True
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        for worker in tuple(self._workers):
            worker.join(timeout=1)
        self._workers.clear()
