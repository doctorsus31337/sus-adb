"""Non-modal controller for dedicated ADB, Objection, and Frida terminals."""

from __future__ import annotations

import queue
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.core.interactive_sessions import InteractiveSessionState
from app.core.script_descriptor import ScriptKind
from app.core.worker import BackgroundWorker
from app.gui.customtkinter_compat import safe_focus, widget_exists


class SessionsCenter(ctk.CTkToplevel):
    SECTIONS = (
        "ADB Shell",
        "Root Shell",
        "Objection",
        "Frida REPL",
        "Frida Trace",
        "Active Sessions",
    )

    def __init__(
        self,
        parent,
        theme,
        manager,
        host_state,
        *,
        target_provider=lambda: None,
        script_library=None,
        open_script_callback=None,
        help_callback=None,
        ui_dispatch=None,
        on_close=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.manager = manager
        self.host_state = host_state
        self.target_provider = target_provider
        self.script_library = script_library
        self.open_script_callback = open_script_callback
        self.help_callback = help_callback
        self._local_ui_queue = None
        self._ui_poll_id = None
        if ui_dispatch is None:
            self._local_ui_queue = queue.Queue()
            self.dispatch = lambda callback, *args: self._local_ui_queue.put((callback, args))
        else:
            self.dispatch = ui_dispatch
        self.on_close = on_close
        self.context = host_state.snapshot()
        self.routed_plan = None
        self.descriptors = ()
        self._workers = set()
        self._closed = False
        self._poll_id = None
        self.title(f"{METADATA.application_name} — Sessions Center")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 650)
        self.geometry(self._center(1180, 780))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build_header()
        self._build_route_bar()
        self._build_tabs()
        self.state_subscription = host_state.subscribe(
            "sessions-center", lambda snapshot: self.apply_snapshot(snapshot)
        )
        self.manager_unsubscribe = manager.subscribe(
            lambda _record: self.dispatch(self.render_sessions)
        )
        self._scan_scripts()
        self.apply_snapshot(self.context)
        self.render_sessions()
        if self._local_ui_queue is not None:
            self._ui_poll_id = self.after(15, self._poll_local_ui)
        self._poll_id = self.after(1000, self._poll_sessions)

    def _poll_local_ui(self):
        if self._closed or self._local_ui_queue is None:
            return
        while True:
            try:
                callback, args = self._local_ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self._ui_poll_id = self.after(15, self._poll_local_ui)

    def _center(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = min(width, screen_width), min(height, screen_height)
        return (
            f"{width}x{height}+{max(0, (screen_width-width)//2)}"
            f"+{max(0, (screen_height-height)//2)}"
        )

    def _build_header(self):
        header = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        for column in range(6):
            header.grid_columnconfigure(column, weight=1)
        ctk.CTkLabel(
            header, text="SESSIONS CENTER", text_color=self.theme["gold"],
            font=("Times New Roman", 24, "bold"),
        ).grid(row=0, column=0, columnspan=5, sticky="w", padx=10, pady=(7, 3))
        ctk.CTkButton(
            header, text="? Help",
            command=lambda: self.help_callback("sessions-center")
            if self.help_callback else None,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"], width=90,
        ).grid(row=0, column=5, sticky="e", padx=10, pady=(7, 3))
        self.header_values = {}
        for column, (key, label) in enumerate(
            (
                ("device", "Device"),
                ("serial", "Serial"),
                ("target", "Target"),
                ("endpoint", "Endpoint"),
                ("mode", "Interface Mode"),
            )
        ):
            cell = ctk.CTkFrame(header, fg_color="transparent")
            cell.grid(row=1, column=column, sticky="ew", padx=6, pady=(2, 7))
            ctk.CTkLabel(
                cell, text=label, text_color=self.theme["muted"],
                font=("Segoe UI", 10, "bold"), anchor="w",
            ).pack(fill="x")
            value = ctk.CTkLabel(
                cell, text="—", text_color=self.theme["gold"], anchor="w",
                wraplength=210,
            )
            value.pack(fill="x")
            self.header_values[key] = value

    def _build_route_bar(self):
        self.route_bar = ctk.CTkFrame(
            self, fg_color=self.theme["panel_alt"], border_width=1,
            border_color=self.theme["border"],
        )
        self.route_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        self.route_bar.grid_columnconfigure(0, weight=1)
        self.route_label = ctk.CTkLabel(
            self.route_bar, text="", text_color=self.theme["gold"],
            anchor="w", justify="left", wraplength=850,
        )
        self.route_label.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        self.route_launch = self._button(
            self.route_bar, "Launch Routed Session", self.launch_routed, 1
        )
        self.route_cancel = self._button(
            self.route_bar, "Clear", self.clear_route, 2
        )
        self.route_bar.grid_remove()

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
            segmented_button_fg_color=self.theme["panel_alt"],
            segmented_button_selected_color=self.theme["red"],
            segmented_button_selected_hover_color=self.theme["red_hover"],
            segmented_button_unselected_color=self.theme["panel_alt"],
            segmented_button_unselected_hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
        self.pages = {name: self.tabs.add(name) for name in self.SECTIONS}
        for page in self.pages.values():
            page.configure(fg_color=self.theme["bg"])
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(1, weight=1)
        self._build_adb()
        self._build_root()
        self._build_objection()
        self._build_frida()
        self._build_trace()
        self._build_active()

    def _button(self, parent, text, command, column=0):
        button = ctk.CTkButton(
            parent, text=text, command=command,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        button.grid(row=0, column=column, sticky="ew", padx=4, pady=5)
        return button

    def _entry(self, parent, placeholder=""):
        return ctk.CTkEntry(
            parent, placeholder_text=placeholder,
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )

    def _combo(self, parent, values):
        combo = ctk.CTkComboBox(
            parent, values=list(values), state="readonly",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            button_color=self.theme["red"], button_hover_color=self.theme["red_hover"],
            dropdown_fg_color=self.theme["panel_alt"], dropdown_hover_color=self.theme["red"],
            text_color=self.theme["text"], dropdown_text_color=self.theme["text"],
        )
        combo.set(values[0])
        combo.configure(command=lambda _value: self.refresh_previews())
        return combo

    def _form(self, page, title, explanation):
        ctk.CTkLabel(
            page, text=title, text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(7, 3))
        body = ctk.CTkFrame(page, fg_color=self.theme["panel_alt"])
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=5)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(7, weight=1)
        ctk.CTkLabel(
            body, text=explanation, text_color=self.theme["muted"],
            anchor="w", justify="left", wraplength=900,
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        preview = ctk.CTkTextbox(
            body, height=150, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], border_width=1,
            border_color=self.theme["border"], wrap="word",
        )
        preview.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=8, pady=7)
        preview.configure(state="disabled")
        return body, preview

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _labeled(self, body, row, label, widget):
        ctk.CTkLabel(
            body, text=label, text_color=self.theme["muted"], anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        widget.grid(row=row, column=1, columnspan=2, sticky="ew", padx=8, pady=4)

    def _build_adb(self):
        body, self.adb_preview = self._form(
            self.pages["ADB Shell"], "ADB Shell",
            "Open an interactive Android shell in a dedicated terminal. "
            "It never occupies the one-shot Console queue.",
        )
        self.adb_launch = self._button(
            body, "Open ADB Shell", lambda: self.launch_plan(self._adb_plan()), 0
        )
        self.adb_launch.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=6)

    def _build_root(self):
        body, self.root_preview = self._form(
            self.pages["Root Shell"], "Existing Root Shell",
            "Available only when root already exists. SUS Companion never acquires root "
            "and never runs su without explicit confirmation.",
        )
        self.root_launch = self._button(body, "Review and Open Root Shell", self.launch_root, 0)
        self.root_launch.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=6)

    def _build_objection(self):
        body, self.objection_preview = self._form(
            self.pages["Objection"], "Objection Session",
            "Agent loading can take time. The session record remains visibly connecting "
            "while the external terminal is prepared.",
        )
        self.objection_target = self._entry(body, "Application package or process")
        self._labeled(body, 1, "Target", self.objection_target)
        self.objection_mode = self._combo(body, ("attach", "spawn"))
        self._labeled(body, 2, "Mode", self.objection_mode)
        self.objection_transport = self._combo(body, ("socket", "usb"))
        self._labeled(body, 3, "Transport", self.objection_transport)
        self.objection_launch = self._button(
            body, "Open Objection Session",
            lambda: self.launch_plan(self._objection_plan()), 0,
        )
        self.objection_launch.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=6)

    def _build_frida(self):
        body, self.frida_preview = self._form(
            self.pages["Frida REPL"], "Frida REPL",
            "Attach to a running target, spawn an application, or use PID attach in "
            "Advanced mode. A selected local script is passed with -l.",
        )
        self.frida_mode = self._combo(body, ("attach", "spawn", "pid"))
        self._labeled(body, 1, "Launch mode", self.frida_mode)
        self.frida_endpoint = self._entry(body)
        self.frida_endpoint.insert(0, "127.0.0.1:27042")
        self.frida_endpoint.bind("<KeyRelease>", lambda _event: self.refresh_previews())
        self._labeled(body, 2, "Endpoint", self.frida_endpoint)
        script_row = ctk.CTkFrame(body, fg_color="transparent")
        script_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5)
        self.script_combo = self._combo(script_row, ("No Script Studio script",))
        self.script_combo.grid(row=0, column=0, columnspan=4, sticky="ew", padx=3)
        for column in range(4):
            script_row.grid_columnconfigure(column, weight=1)
        select_button = self._button(
            script_row, "Select Script Studio Script", self.select_library_script, 0
        )
        select_button.grid(row=1, column=0, sticky="ew", padx=3, pady=4)
        browse_button = self._button(script_row, "Browse Script…", self.browse_script, 1)
        browse_button.grid(row=1, column=1, sticky="ew", padx=3, pady=4)
        copy_button = self._button(script_row, "Copy Script Path", self.copy_script_path, 2)
        copy_button.grid(row=1, column=2, sticky="ew", padx=3, pady=4)
        open_button = self._button(script_row, "Open in Script Studio", self.open_script, 3)
        open_button.grid(row=1, column=3, sticky="ew", padx=3, pady=4)
        self.frida_launch = self._button(
            body, "Open Frida REPL", lambda: self.launch_plan(self._frida_plan()), 0
        )
        self.frida_launch.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=6)

    def _build_trace(self):
        body, self.trace_preview = self._form(
            self.pages["Frida Trace"], "Frida Trace",
            "Trace an explicitly selected target in a dedicated terminal. "
            "The trace remains active until interrupted or exited.",
        )
        self.trace_mode = self._combo(body, ("attach", "spawn", "pid"))
        self._labeled(body, 1, "Launch mode", self.trace_mode)
        self.trace_endpoint = self._entry(body)
        self.trace_endpoint.insert(0, "127.0.0.1:27042")
        self.trace_endpoint.bind("<KeyRelease>", lambda _event: self.refresh_previews())
        self._labeled(body, 2, "Endpoint", self.trace_endpoint)
        self.trace_pattern = self._entry(body, "Function pattern, for example open*")
        self.trace_pattern.bind("<KeyRelease>", lambda _event: self.refresh_previews())
        self._labeled(body, 3, "Trace pattern", self.trace_pattern)
        self.trace_launch = self._button(
            body, "Open Frida Trace", lambda: self.launch_plan(self._trace_plan()), 0
        )
        self.trace_launch.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=6)

    def _build_active(self):
        page = self.pages["Active Sessions"]
        ctk.CTkLabel(
            page, text="Active and Recent Sessions", text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(7, 3))
        body = ctk.CTkFrame(page, fg_color=self.theme["panel_alt"])
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=5)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(3, weight=1)
        self.session_selector = self._combo(body, ("No sessions",))
        self.session_selector.grid(row=0, column=0, sticky="ew", padx=8, pady=5)
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=5)
        for column in range(5):
            actions.grid_columnconfigure(column, weight=1)
        self._button(actions, "Reconnect", self.reconnect_selected, 0)
        self._button(actions, "Interrupt", self.interrupt_selected, 1)
        self._button(actions, "Terminate", self.terminate_selected, 2)
        self._button(actions, "Close Record", self.close_selected, 3)
        self._button(actions, "Copy Diagnostics", self.copy_diagnostics, 4)
        recovery_actions = ctk.CTkFrame(body, fg_color="transparent")
        recovery_actions.grid(row=2, column=0, sticky="ew", padx=5)
        for column in range(3):
            recovery_actions.grid_columnconfigure(column, weight=1)
        self._button(
            recovery_actions, "Check Connection",
            self.check_selected_connection, 0,
        )
        self._button(
            recovery_actions, "Repair Managed Forwarding",
            self.repair_selected_forwarding, 1,
        )
        self._button(
            recovery_actions, "Technical Details",
            self.show_technical_details, 2,
        )
        self.sessions_text = ctk.CTkTextbox(
            body, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], border_width=1,
            border_color=self.theme["border"], wrap="word",
        )
        self.sessions_text.grid(row=3, column=0, sticky="nsew", padx=8, pady=7)
        self.sessions_text.configure(state="disabled")

    def _selected(self):
        return self.context.selected_device

    def _serial(self):
        return self.context.selected_serial

    def _target(self):
        return self.target_provider()

    def _target_text(self):
        target = self._target()
        return (
            getattr(target, "identifier", None)
            or getattr(target, "name", "")
            or ""
        )

    def _adb_plan(self):
        return self.manager.build_adb_shell(self._serial())

    def _objection_plan(self):
        target = self.objection_target.get().strip() or self._target_text()
        return self.manager.build_objection(
            self._serial(), target,
            spawn=self.objection_mode.get() == "spawn",
            transport=self.objection_transport.get(),
        )

    def _selected_script_path(self):
        value = self.script_combo.get()
        descriptor = next((item for item in self.descriptors if item.name == value), None)
        return descriptor.path if descriptor else getattr(self, "_browsed_script", "")

    def _frida_plan(self):
        return self.manager.build_frida(
            self._serial(), self._target(), mode=self.frida_mode.get(),
            endpoint=self.frida_endpoint.get().strip() or "127.0.0.1:27042",
            script_path=self._selected_script_path(),
        )

    def _trace_plan(self):
        return self.manager.build_frida(
            self._serial(), self._target(), mode=self.trace_mode.get(),
            endpoint=self.trace_endpoint.get().strip() or "127.0.0.1:27042",
            trace=True, trace_pattern=self.trace_pattern.get(),
        )

    def _plan_text(self, plan):
        return (
            f"Session type: {plan.session_type.value}\n"
            f"Selected serial: {plan.serial or 'None'}\n"
            f"Target: {plan.target or 'None'}\n"
            f"Endpoint: {plan.endpoint or 'None'}\n"
            f"Executable: {plan.executable or 'Unresolved'}\n"
            f"Mode: {plan.attach_mode or 'interactive'}\n"
            f"Script: {plan.script_path or 'None'}\n"
            f"Prerequisites: {', '.join(plan.prerequisites) or 'Review command'}\n"
            f"Ready: {plan.ready}\n"
            + (f"Errors: {'; '.join(plan.errors)}\n" if plan.errors else "")
            + f"\nGuided explanation:\n{plan.explanation}\n\n"
            f"Advanced argv:\n{plan.preview()}"
        )

    def apply_snapshot(self, snapshot):
        if self._closed or snapshot.generation < self.context.generation:
            return
        old_serial = self.context.selected_serial
        self.context = snapshot
        selected = snapshot.selected_device
        target = self._target()
        values = {
            "device": selected.display_name if selected else "None",
            "serial": snapshot.selected_serial or "None",
            "target": getattr(target, "display_label", "None") if target else "None",
            "endpoint": "127.0.0.1:27042",
            "mode": snapshot.interface_mode.title(),
        }
        for key, value in values.items():
            self.header_values[key].configure(text=value)
        target_text = self._target_text()
        if target_text and not self.objection_target.get():
            self.objection_target.insert(0, target_text)
        if old_serial and old_serial != snapshot.selected_serial:
            self.clear_route()
        self.refresh_previews()

    def refresh_previews(self):
        plans = (
            (self.adb_preview, self._adb_plan()),
            (
                self.root_preview,
                self.manager.build_adb_shell(
                    self._serial(), root=True,
                    root_available=bool(self._selected() and self._selected().root_available),
                    root_confirmed=False,
                ),
            ),
            (self.objection_preview, self._objection_plan()),
            (self.frida_preview, self._frida_plan()),
            (self.trace_preview, self._trace_plan()),
        )
        for widget, plan in plans:
            self._set_text(widget, self._plan_text(plan))
        selected = self._selected()
        usable = bool(selected and selected.usable)
        self.adb_launch.configure(state="normal" if usable else "disabled")
        self.root_launch.configure(
            state="normal" if usable and selected.root_available else "disabled"
        )

    def open_route(self, route):
        self.routed_plan = self.manager.plan_from_route(
            route, self._serial(), self._target()
        )
        section = {
            "adb-shell": "ADB Shell",
            "adb-logcat": "Active Sessions",
            "objection": "Objection",
            "frida-repl": "Frida REPL",
            "frida-trace": "Frida Trace",
        }.get(route.session_type, "Active Sessions")
        self.tabs.set(section)
        self.route_label.configure(text=self._plan_text(self.routed_plan))
        self.route_launch.configure(
            state="normal" if self.routed_plan.ready else "disabled"
        )
        self.route_bar.grid()
        self.deiconify()
        self.lift()

    def clear_route(self):
        self.routed_plan = None
        self.route_bar.grid_remove()

    def launch_routed(self):
        if self.routed_plan:
            self.launch_plan(self.routed_plan)

    def launch_root(self):
        selected = self._selected()
        if not selected or not selected.root_available:
            return
        confirmed = messagebox.askyesno(
            "Open Existing Root Shell",
            f"Open su in a dedicated shell on {selected.serial}?\n\n"
            "SUS Companion will not acquire root or change the device.",
            parent=self,
        )
        if confirmed:
            self.launch_plan(
                self.manager.build_adb_shell(
                    selected.serial, root=True, root_available=True,
                    root_confirmed=True,
                )
            )

    def launch_plan(self, plan):
        self._set_text(
            self.sessions_text,
            "Preparing dedicated external terminal…\n\n" + self._plan_text(plan),
        )
        self.tabs.set("Active Sessions")
        self._run(lambda: self.manager.launch(plan), self._operation_done)

    def _run(self, target, callback):
        worker = None

        def finished(result):
            self._workers.discard(worker)
            self.dispatch(callback, result)

        worker = BackgroundWorker(target, callback=finished)
        self._workers.add(worker)
        worker.start()

    def _operation_done(self, result):
        if self._closed:
            return
        self.render_sessions()
        if not result.ok:
            self._set_text(
                self.sessions_text,
                f"Session operation failed.\n\n{result.error}\n\n"
                + (self.manager.diagnostics(result.record.session_id) if result.record else ""),
            )

    def _scan_scripts(self):
        if not self.script_library:
            return
        result = self.script_library.scan()
        self.descriptors = tuple(
            item for item in result.descriptors
            if item.kind is ScriptKind.FRIDA
        ) if result.ok else ()
        values = [item.name for item in self.descriptors] or ["No Script Studio script"]
        self.script_combo.configure(values=values)
        self.script_combo.set(values[0])

    def browse_script(self):
        path = filedialog.askopenfilename(
            parent=self, title="Select local Frida script",
            filetypes=(("Frida JavaScript", "*.js *.ts"), ("All files", "*")),
        )
        if path:
            self._browsed_script = str(Path(path).expanduser().resolve())
            self.script_combo.configure(values=(Path(path).name,))
            self.script_combo.set(Path(path).name)
            self.refresh_previews()

    def select_library_script(self):
        self._scan_scripts()
        safe_focus(self.script_combo)
        self.refresh_previews()

    def select_script(self, descriptor):
        self._scan_scripts()
        match = next(
            (
                item for item in self.descriptors
                if item.script_id == descriptor.script_id
            ),
            None,
        )
        if match is not None:
            self.script_combo.set(match.name)
            self._browsed_script = ""
        else:
            self._browsed_script = str(Path(descriptor.path).resolve())
            self.script_combo.configure(values=(descriptor.name,))
            self.script_combo.set(descriptor.name)
        self.tabs.set("Frida REPL")
        self.refresh_previews()
        self.deiconify()
        self.lift()

    def copy_script_path(self):
        path = self._selected_script_path()
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)

    def open_script(self):
        value = self.script_combo.get()
        descriptor = next((item for item in self.descriptors if item.name == value), None)
        if descriptor and self.open_script_callback:
            self.open_script_callback(descriptor)

    def render_sessions(self):
        if self._closed or not widget_exists(self):
            return
        records = self.manager.refresh_states()
        labels = [
            f"{record.session_id} · {record.session_type.value} · {record.state.value}"
            for record in records
        ] or ["No sessions"]
        current = self.session_selector.get()
        self.session_selector.configure(values=labels)
        self.session_selector.set(current if current in labels else labels[-1])
        text = "\n\n".join(
            f"{record.session_id}\n"
            f"Type: {record.session_type.value} · State: {record.state.value}\n"
            f"Serial: {record.serial or 'None'} · Target: {record.target or 'None'}\n"
            f"Started: {record.start_time}\n"
            f"Backend: {record.backend or 'Preparing'}\n"
            f"Prompt ready: {record.prompt_ready_time or 'Not observable'}\n"
            f"Stages: {', '.join(f'{name}={value}' for name, value in record.stages) or 'None'}\n"
            f"Error: {record.last_error or 'None'}"
            for record in records
        ) or "No interactive sessions have been launched."
        self._set_text(self.sessions_text, text)

    def _selected_session_id(self):
        return self.session_selector.get().split(" · ", 1)[0] if self.manager.list() else ""

    def reconnect_selected(self):
        session_id = self._selected_session_id()
        if session_id:
            self._run(lambda: self.manager.reconnect(session_id), self._operation_done)

    def interrupt_selected(self):
        session_id = self._selected_session_id()
        if session_id:
            self._operation_done(self.manager.interrupt(session_id))

    def terminate_selected(self):
        session_id = self._selected_session_id()
        if session_id and messagebox.askyesno(
            "Terminate Session",
            "Terminate the tracked external terminal process? Closing a record alone does not terminate it.",
            parent=self,
        ):
            self._operation_done(self.manager.terminate(session_id))

    def close_selected(self):
        session_id = self._selected_session_id()
        if session_id:
            self._operation_done(self.manager.close_record(session_id))

    def copy_diagnostics(self):
        session_id = self._selected_session_id()
        if session_id:
            self.clipboard_clear()
            self.clipboard_append(self.manager.diagnostics(session_id))

    def check_selected_connection(self):
        session_id = self._selected_session_id()
        if session_id:
            self._run(
                lambda: self.manager.check_objection_connection(session_id),
                self._recovery_done,
            )

    def repair_selected_forwarding(self):
        session_id = self._selected_session_id()
        if session_id:
            self._run(
                lambda: self.manager.repair_objection_forwarding(session_id),
                self._repair_done,
            )

    def _recovery_done(self, report):
        if report is None:
            self._set_text(
                self.sessions_text,
                "Select an Objection session to check its connection.",
            )
            return
        self._set_text(self.sessions_text, report.concise())

    def _repair_done(self, value):
        if value is None:
            self._set_text(
                self.sessions_text,
                "Select an Objection session before repairing managed forwarding.",
            )
            return
        repair, report = value
        prefix = (
            f"Managed ports: {', '.join(repair.managed_ports) or 'None'}\n"
            f"Repaired: {', '.join(repair.repaired_ports) or 'None'}\n"
            f"Preserved unchanged: {', '.join(repair.preserved_ports) or 'None'}\n\n"
        )
        self._set_text(self.sessions_text, prefix + report.concise())

    def show_technical_details(self):
        session_id = self._selected_session_id()
        if session_id:
            self._set_text(
                self.sessions_text,
                self.manager.diagnostics(session_id),
            )

    def _poll_sessions(self):
        if self._closed:
            return
        self.render_sessions()
        self._poll_id = self.after(1000, self._poll_sessions)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        if self._ui_poll_id is not None:
            try:
                self.after_cancel(self._ui_poll_id)
            except Exception:
                pass
            self._ui_poll_id = None
        if self.state_subscription:
            self.state_subscription.cancel()
            self.state_subscription = None
        if self.manager_unsubscribe:
            self.manager_unsubscribe()
            self.manager_unsubscribe = None
        for worker in tuple(self._workers):
            worker.join(1)
        self._workers.clear()
        safe_focus(self.master)
        if self.on_close:
            self.on_close()
        self.destroy()
