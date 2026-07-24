"""Host-owned Device Rescue workspace; plugins receive no filesystem or ADB objects."""

from __future__ import annotations

import queue
from pathlib import PurePosixPath
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.core.device_recovery_service import (
    PUBLIC_PRESETS,
    RecoveryCancellation,
    RecoveryLimits,
)
from app.core.worker import BackgroundWorker


def format_bytes(value: int | None) -> str:
    if value is None:
        return "Unknown"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{int(value)} B"


class DeviceRecoveryPanel(ctk.CTkFrame):
    SECTIONS = (
        "Overview",
        "Connection",
        "Storage Scan",
        "Recovery Plan",
        "Files",
        "Copy Queue",
        "Results",
        "Guidance",
    )

    def __init__(
        self,
        parent,
        theme,
        service,
        *,
        destination_chooser=None,
        manifest_chooser=None,
        help_callback=None,
        confirm_device_change=None,
        ui_dispatch=None,
    ):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme = theme
        self.service = service
        self.destination_chooser = destination_chooser or (
            lambda: filedialog.askdirectory(parent=self.winfo_toplevel(), title="Choose Recovery Destination")
        )
        self.manifest_chooser = manifest_chooser or (
            lambda: filedialog.askopenfilename(
                parent=self.winfo_toplevel(),
                title="Select Recovery Manifest",
                filetypes=(("Recovery manifest", "recovery-manifest.json"), ("JSON", "*.json")),
            )
        )
        self.help_callback = help_callback
        self.confirm_device_change = confirm_device_change or (
            lambda title, message: messagebox.askyesno(
                title, message, parent=self.winfo_toplevel()
            )
        )
        self._local_ui_queue = None
        self._poll_id = None
        if ui_dispatch is None:
            self._local_ui_queue = queue.Queue()
            self.dispatch = lambda callback, *args: self._local_ui_queue.put((callback, args))
            self._poll_id = self.after(15, self._poll_local_ui)
        else:
            self.dispatch = ui_dispatch
        self.context = None
        self.serial = ""
        self.device_state = "unavailable"
        self.private_allowed = False
        self.scan = None
        self.plan = None
        self.result = None
        self.cancellation = None
        self.worker = None
        self._active_serial = ""
        self._closed = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_tabs()
        self._set_guidance()
        self._sync_actions()

    def _poll_local_ui(self):
        if self._closed or self._local_ui_queue is None:
            return
        while True:
            try:
                callback, args = self._local_ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self._poll_id = self.after(15, self._poll_local_ui)

    def _build_header(self):
        header = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(4, 2))
        for column in range(4):
            header.grid_columnconfigure(column, weight=1)
        fields = (
            ("device", "Device"),
            ("serial", "Serial"),
            ("adb", "ADB State"),
            ("authorization", "Authorization"),
            ("mode", "Connection Mode"),
            ("source", "Storage Source"),
            ("destination", "Destination"),
            ("scan", "Scan Status"),
            ("queue", "Queue Progress"),
        )
        self.header_values = {}
        for index, (key, label) in enumerate(fields):
            row, column = divmod(index, 3)
            cell = ctk.CTkFrame(header, fg_color="transparent")
            cell.grid(row=row, column=column, sticky="ew", padx=7, pady=3)
            ctk.CTkLabel(
                cell, text=label, text_color=self.theme["muted"], anchor="w",
                font=("Segoe UI", 10, "bold"),
            ).pack(fill="x")
            value = ctk.CTkLabel(cell, text="—", text_color=self.theme["gold"], anchor="w")
            value.pack(fill="x")
            self.header_values[key] = value
        self.warning = ctk.CTkLabel(
            header,
            text="Bootloader unlocking commonly wipes user data and must not be used as a recovery technique.",
            text_color=self.theme["error"],
            anchor="w",
            wraplength=1000,
        )
        self.warning.grid(row=3, column=0, columnspan=4, sticky="ew", padx=7, pady=(3, 7))
        ctk.CTkButton(
            header, text="Help",
            command=lambda: self.help_callback("device-rescue")
            if self.help_callback else None,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"], width=90,
        ).grid(row=0, column=3, rowspan=3, sticky="e", padx=7, pady=5)

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=self.theme["panel"],
            segmented_button_fg_color=self.theme["panel_alt"],
            segmented_button_selected_color=self.theme["red"],
            segmented_button_selected_hover_color=self.theme["red_hover"],
            segmented_button_unselected_color=self.theme["panel_alt"],
            segmented_button_unselected_hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=5, pady=(2, 5))
        self.pages = {name: self.tabs.add(name) for name in self.SECTIONS}
        self.section_serial_labels = {}
        for page in self.pages.values():
            page.configure(fg_color=self.theme["bg"])
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(1, weight=1)
        self._build_overview()
        self._build_connection()
        self._build_scan()
        self._build_plan()
        self._build_files()
        self._build_queue()
        self._build_results()
        self._build_guidance()

    def _textbox(self, page, row=1):
        text = ctk.CTkTextbox(
            page,
            fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"],
            border_width=1,
            border_color=self.theme["border"],
            wrap="word",
        )
        text.grid(row=row, column=0, sticky="nsew", padx=8, pady=8)
        return text

    def _title(self, page, value):
        title_bar = ctk.CTkFrame(page, fg_color="transparent")
        title_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(7, 2))
        title_bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            title_bar, text=value, text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        identity = ctk.CTkLabel(
            title_bar, text="Serial: None", text_color=self.theme["gold"],
            font=("Consolas", 11, "bold"), anchor="e",
        )
        identity.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.section_serial_labels[value] = identity

    def _button(self, parent, text, command, column=0):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
            border_width=1,
            border_color=self.theme["gold_dark"],
        )
        button.grid(row=0, column=column, sticky="ew", padx=3, pady=4)
        return button

    def _build_overview(self):
        page = self.pages["Overview"]
        self._title(page, "Authorized Selected-File Recovery")
        self.overview_text = self._textbox(page)

    def _build_connection(self):
        page = self.pages["Connection"]
        self._title(page, "Available Connection Route")
        self.connection_text = self._textbox(page)

    def _build_scan(self):
        page = self.pages["Storage Scan"]
        self._title(page, "Shared Storage Inventory")
        controls = ctk.CTkFrame(page, fg_color=self.theme["panel_alt"])
        controls.grid(row=1, column=0, sticky="ew", padx=8, pady=5)
        controls.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(controls, text="Storage root", text_color=self.theme["muted"]).grid(row=0, column=0, padx=5)
        self.source_entry = ctk.CTkEntry(
            controls, fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.source_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.source_entry.insert(0, "/sdcard")
        self.scan_button = self._button(controls, "Scan Storage", self.start_scan, 2)
        ctk.CTkLabel(controls, text="Custom explicit paths", text_color=self.theme["muted"]).grid(row=1, column=0, padx=5)
        self.custom_entry = ctk.CTkEntry(
            controls, placeholder_text="/sdcard/example.txt, /storage/emulated/0/example-folder",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.custom_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        preset_frame = ctk.CTkFrame(controls, fg_color="transparent")
        preset_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=4)
        self.preset_vars = {}
        for index, name in enumerate(PUBLIC_PRESETS):
            variable = ctk.BooleanVar(value=name in {"DCIM", "Pictures", "Documents", "Download"})
            self.preset_vars[name] = variable
            ctk.CTkCheckBox(
                preset_frame, text=name, variable=variable,
                fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
                border_color=self.theme["gold_dark"], text_color=self.theme["text"],
            ).grid(row=index // 5, column=index % 5, sticky="w", padx=5, pady=3)
        page.grid_rowconfigure(2, weight=1)
        self.scan_text = self._textbox(page, 2)

    def _build_plan(self):
        page = self.pages["Recovery Plan"]
        self._title(page, "Destination Preflight and Recovery Plan")
        controls = ctk.CTkFrame(page, fg_color=self.theme["panel_alt"])
        controls.grid(row=1, column=0, sticky="ew", padx=8, pady=5)
        controls.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(controls, text="Host destination", text_color=self.theme["muted"]).grid(row=0, column=0, padx=5)
        self.destination_entry = ctk.CTkEntry(
            controls, fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.destination_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.destination_button = self._button(controls, "Choose Destination", self.choose_destination, 2)
        options = ctk.CTkFrame(controls, fg_color="transparent")
        options.grid(row=1, column=0, columnspan=3, sticky="ew", padx=4)
        ctk.CTkLabel(options, text="Safety headroom", text_color=self.theme["muted"]).grid(row=0, column=0, padx=4)
        self.headroom = ctk.CTkComboBox(
            options, values=["10%", "15%", "20%", "25%"], state="readonly",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            button_color=self.theme["red"], button_hover_color=self.theme["red_hover"],
            dropdown_fg_color=self.theme["panel_alt"], dropdown_hover_color=self.theme["red"],
            text_color=self.theme["text"], dropdown_text_color=self.theme["text"], width=100,
        )
        self.headroom.grid(row=0, column=1, padx=4)
        self.headroom.set("10%")
        ctk.CTkLabel(options, text="Duplicates", text_color=self.theme["muted"]).grid(row=0, column=2, padx=4)
        self.duplicate = ctk.CTkComboBox(
            options, values=["skip", "rename", "replace"], state="readonly",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            button_color=self.theme["red"], button_hover_color=self.theme["red_hover"],
            dropdown_fg_color=self.theme["panel_alt"], dropdown_hover_color=self.theme["red"],
            text_color=self.theme["text"], dropdown_text_color=self.theme["text"], width=110,
        )
        self.duplicate.grid(row=0, column=3, padx=4)
        self.duplicate.set("skip")
        self.unknown_ack = ctk.BooleanVar(value=False)
        self.replace_ack = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            options, text="Acknowledge unknown estimate for bounded selected files",
            variable=self.unknown_ack, fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            border_color=self.theme["gold_dark"], text_color=self.theme["text"],
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=4, pady=4)
        ctk.CTkCheckBox(
            options, text="Explicitly confirm replace",
            variable=self.replace_ack, fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            border_color=self.theme["gold_dark"], text_color=self.theme["text"],
        ).grid(row=1, column=3, sticky="w", padx=4, pady=4)
        self.plan_button = self._button(controls, "Build Recovery Plan", self.build_plan, 3)
        self.plan_button.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=6)
        page.grid_rowconfigure(2, weight=1)
        self.plan_text = self._textbox(page, 2)

    def _build_files(self):
        page = self.pages["Files"]
        self._title(page, "Selected Files and Folders")
        self.files_text = self._textbox(page)

    def _build_queue(self):
        page = self.pages["Copy Queue"]
        self._title(page, "Bounded Recovery Queue")
        controls = ctk.CTkFrame(page, fg_color=self.theme["panel_alt"])
        controls.grid(row=1, column=0, sticky="ew", padx=8, pady=5)
        for column in range(3):
            controls.grid_columnconfigure(column, weight=1)
        self.start_button = self._button(controls, "Start Recovery", self.start_recovery, 0)
        self.cancel_button = self._button(controls, "Cancel", self.cancel_recovery, 1)
        self.resume_button = self._button(controls, "Resume Same Serial…", self.resume_recovery, 2)
        self.progress = ctk.CTkProgressBar(
            controls, fg_color=self.theme["terminal_bg"], progress_color=self.theme["red"],
            border_color=self.theme["gold_dark"], border_width=1,
        )
        self.progress.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=6)
        self.progress.set(0)
        self.current_path = ctk.CTkLabel(
            controls, text="Queue idle.", text_color=self.theme["gold"], anchor="w", wraplength=900,
        )
        self.current_path.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=4)
        page.grid_rowconfigure(2, weight=1)
        self.queue_text = self._textbox(page, 2)

    def _build_results(self):
        page = self.pages["Results"]
        self._title(page, "Recovery Results and Manifest")
        self.results_text = self._textbox(page)

    def _build_guidance(self):
        page = self.pages["Guidance"]
        self._title(page, "Safe Recovery Guidance")
        self.guidance_text = self._textbox(page)

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _set_guidance(self):
        self._set_text(
            self.guidance_text,
            "Supported routes:\n"
            "• ADB-authorized shared internal storage\n"
            "• Recovery-mode ADB when already available\n"
            "• Existing root only when separately permitted by assessment scope\n"
            "• MTP/manual transfer guidance when ADB is unavailable\n"
            "• Screen repair or manual-interaction guidance\n\n"
            "This workspace never roots, unlocks, flashes, wipes, bypasses authentication or "
            "encryption, silently changes Android profiles, deletes source files, or automatically "
            "opens recovered files.\n\n"
            "Bootloader unlocking commonly wipes user data and must not be used as a recovery technique.",
        )

    def apply_context(self, context):
        if self._closed:
            return
        selected = getattr(context, "selected_device", {}) or {}
        serial = selected.get("serial", "")
        if self.serial and serial != self.serial and self.worker is not None:
            self.cancel_recovery(interrupted=True)
        if serial != self.serial:
            self._clear_recovery_state(
                "Device disconnected; completed state remains only in its manifest."
                if not serial and self.serial else
                "Selected serial changed; stale scan, plan, queue, and results were cleared."
            )
        self.context = context
        self.serial = serial
        self.device_state = selected.get("state", "unavailable")
        scope = getattr(context, "assessment_scope", {}) or {}
        allowed = set(scope.get("allowed_actions", ()))
        self.private_allowed = bool(
            selected.get("root_available")
            and getattr(context, "session_state", "none") == "active"
            and {"sensitive-data-inspection", "storage-inspection"} <= allowed
        )
        authorized = bool(selected.get("authorized"))
        values = {
            "device": selected.get("display_name") or "None",
            "serial": serial or "None",
            "adb": getattr(context, "adb_state", self.device_state).title(),
            "authorization": "Authorized" if authorized else "Unavailable",
            "mode": {
                "device": "ADB",
                "recovery": "Recovery ADB",
                "sideload": "ADB Sideload",
                "bootloader": "Bootloader",
                "fastbootd": "Fastbootd",
            }.get(self.device_state, self.device_state.title()),
            "source": self.source_entry.get() or "/sdcard",
            "destination": self.destination_entry.get() or "Not selected",
            "scan": "Complete" if self.scan else "Not run",
            "queue": "Running" if self.worker else "Idle",
        }
        for key, value in values.items():
            self.header_values[key].configure(text=value)
        for label in self.section_serial_labels.values():
            label.configure(text=f"Serial: {serial or 'None'}")
        if authorized:
            connection = f"Selected device {serial} is available through {values['mode']}."
        elif self.device_state == "unauthorized":
            connection = "ADB authorization is required on the device before scanning."
        elif self.device_state in {"bootloader", "fastbootd"}:
            connection = "ADB file recovery is unavailable in this mode. Do not unlock the bootloader for recovery."
        else:
            connection = "ADB is unavailable. Use MTP/manual transfer or repair the screen for authorized interaction."
        self._set_text(self.connection_text, connection)
        self._set_text(
            self.overview_text,
            f"Selected device: {values['device']}\nSerial: {values['serial']}\n"
            f"ADB state: {values['adb']}\nAuthorization: {values['authorization']}\n\n"
            "Refresh and device selection never start a scan or copy action.",
        )
        self._sync_actions()

    def has_recovery_work(self):
        return bool(self.worker or self.scan or self.plan or self.result)

    def can_change_device(self, serial):
        if not self.serial or serial == self.serial or not self.has_recovery_work():
            return True
        return bool(self.confirm_device_change(
            "Change Recovery Device",
            f"Device Rescue contains scan, queue, or result state for {self.serial}.\n\n"
            f"Changing to {serial or 'no device'} clears that state and never transfers it "
            "to the new serial. Completed files and an existing manifest remain on disk.\n\n"
            "Change the selected device?",
        ))

    def _clear_recovery_state(self, reason):
        self.scan = None
        self.plan = None
        self.result = None
        self.cancellation = None
        self.progress.set(0)
        self.current_path.configure(text=reason)
        self._set_text(self.scan_text, "Run a storage scan for the explicitly selected device.")
        self._set_text(self.plan_text, "No recovery plan has been built.")
        self._set_text(self.files_text, "No files are selected.")
        self._set_text(self.queue_text, reason)
        self._set_text(self.results_text, "No results for the current selected serial.")

    def _custom_paths(self):
        raw = self.custom_entry.get().replace("\n", ",")
        return tuple(dict.fromkeys(value.strip() for value in raw.split(",") if value.strip()))

    def _usable(self):
        return bool(self.serial and self.device_state in {"device", "recovery", "sideload"})

    def _sync_actions(self):
        active = self.worker is not None
        self.scan_button.configure(state="normal" if self._usable() and not active else "disabled")
        self.plan_button.configure(state="normal" if self.scan and not active else "disabled")
        self.start_button.configure(state="normal" if self.plan and self.plan.ok and not active else "disabled")
        self.cancel_button.configure(state="normal" if active else "disabled")
        self.resume_button.configure(state="normal" if self.plan and not active else "disabled")
        self.destination_button.configure(state="disabled" if active else "normal")

    def _launch(self, target, callback):
        if self.worker is not None:
            return False
        worker = None

        def finished(result):
            self.dispatch(callback, result)

        worker = BackgroundWorker(target, callback=finished)
        self.worker = worker
        self._sync_actions()
        worker.start()
        return True

    def start_scan(self):
        if not self._usable():
            return
        serial = self.serial
        self._active_serial = serial
        root = self.source_entry.get().strip() or "/sdcard"
        self.header_values["scan"].configure(text="Scanning…")
        self._set_text(self.scan_text, f"Scanning {root} on {serial}…")
        self._launch(
            lambda: self.service.scan_shared_storage(
                serial, root, custom_paths=self._custom_paths(), limits=RecoveryLimits(),
                allow_private=self.private_allowed,
            ),
            self._finish_scan,
        )

    def _finish_scan(self, result):
        self.worker = None
        self._active_serial = ""
        if self._closed:
            return
        if result.serial != self.serial:
            self.header_values["scan"].configure(text="Stale result ignored")
            self._sync_actions()
            return
        self.scan = result
        self.plan = None
        self.header_values["scan"].configure(text="Complete" if result.ok else "Failed")
        self.header_values["source"].configure(text=result.resolved_path or result.requested_path)
        lines = [
            f"Requested: {result.requested_path}",
            f"Resolved canonical path: {result.resolved_path or 'Unavailable'}",
            f"Identity: {result.identity or 'Not observable'}",
            f"Folders: {result.folder_count}",
            f"Files: {result.file_count}",
            f"Loose root files: {result.loose_file_count}",
            f"Estimated bytes: {format_bytes(result.estimated_bytes)}",
            "",
            "Top-level inventory:",
            *(f"• {entry.kind}: {entry.source}" for entry in result.top_level_entries),
        ]
        if result.errors:
            lines.extend(("", "Errors:", *(f"• {error}" for error in result.errors)))
        self._set_text(self.scan_text, "\n".join(lines))
        self._render_files()
        self._sync_actions()

    def _selected_sources(self):
        if not self.scan:
            return ()
        base = self.scan.resolved_path.rstrip("/")
        selected = [f"{base}/{name}" for name, variable in self.preset_vars.items() if variable.get()]
        selected.extend(self._custom_paths())
        return tuple(dict.fromkeys(selected))

    def _render_files(self):
        if not self.scan:
            self._set_text(self.files_text, "No scan results.")
            return
        selected = self._selected_sources()
        lines = [f"Selected source: {path}" for path in selected]
        lines.extend(
            f"{entry.kind.upper():9} {format_bytes(entry.size):>12}  {entry.source}"
            for entry in self.scan.entries
            if any(self.service._within(entry.source, source) for source in selected)
        )
        self._set_text(self.files_text, "\n".join(lines) or "Select at least one preset or custom path.")

    def choose_destination(self):
        path = self.destination_chooser()
        if not path:
            return
        self.destination_entry.delete(0, "end")
        self.destination_entry.insert(0, path)
        self.header_values["destination"].configure(text=path)

    def build_plan(self):
        if not self.scan:
            return
        selected = self._selected_sources()
        bounded = bool(selected) and all(
            any(entry.source == source and entry.kind == "file" for entry in self.scan.entries)
            for source in selected
        )
        priorities = {
            source: 10 if PurePosixPath(source).name in {"DCIM", "Pictures", "Documents"} else 100
            for source in selected
        }
        headroom = float(self.headroom.get().rstrip("%")) / 100
        self.plan = self.service.build_plan(
            self.scan,
            selected,
            self.destination_entry.get(),
            safety_headroom=headroom,
            duplicate_policy=self.duplicate.get(),
            replace_confirmed=self.replace_ack.get(),
            acknowledge_unknown=self.unknown_ack.get(),
            bounded_selected_files=bounded,
            priorities=priorities,
        )
        destination = self.plan.destination
        lines = [
            f"Status: {'Ready' if self.plan.ok else 'Blocked'}",
            f"Serial: {self.plan.serial}",
            f"Selected sources: {len(self.plan.sources)}",
            f"Queued files: {len(self.plan.entries)}",
            f"Destination: {destination.recovery_path or destination.base_path}",
            f"Destination drive: {destination.drive or 'Unknown'}",
            f"Writable: {destination.writable}",
            f"Free bytes: {format_bytes(destination.free_bytes)}",
            f"Required bytes: {format_bytes(destination.required_bytes)}",
            f"Safety buffer: {format_bytes(destination.safety_bytes)}",
            f"Duplicate policy: {self.plan.duplicate_policy}",
        ]
        if self.plan.error:
            lines.extend(("", f"Blocked: {self.plan.error}"))
        self._set_text(self.plan_text, "\n".join(lines))
        self.header_values["destination"].configure(text=destination.recovery_path or "Not ready")
        self._render_files()
        self._sync_actions()

    def start_recovery(self):
        if not self.plan or not self.plan.ok:
            return
        if self.serial != self.plan.serial:
            self._set_text(self.queue_text, "Selected serial changed. Rebuild the recovery plan.")
            return
        self.cancellation = RecoveryCancellation()
        self._active_serial = self.plan.serial
        self.tabs.set("Copy Queue")
        self._set_text(self.queue_text, "Starting bounded recovery queue…")
        self._launch(
            lambda: self.service.execute(
                self.plan, cancellation=self.cancellation,
                progress=lambda value: self.dispatch(self._progress, value),
            ),
            self._finish_recovery,
        )

    def resume_recovery(self):
        if not self.plan:
            return
        manifest = self.manifest_chooser()
        if not manifest:
            return
        self.cancellation = RecoveryCancellation()
        self._active_serial = self.plan.serial
        self.tabs.set("Copy Queue")
        self._set_text(self.queue_text, "Validating same-serial recovery manifest…")
        self._launch(
            lambda: self.service.resume(
                self.plan, manifest, cancellation=self.cancellation,
                progress=lambda value: self.dispatch(self._progress, value),
            ),
            self._finish_recovery,
        )

    def _progress(self, value):
        if self._closed or value.serial != self.serial:
            return
        ratio = value.files_completed / value.files_total if value.files_total else 0
        self.progress.set(max(0, min(1, ratio)))
        self.current_path.configure(text=f"{value.state.title()}: {value.current_path}")
        self.header_values["queue"].configure(
            text=f"{value.files_completed}/{value.files_total} · {format_bytes(value.bytes_completed)}"
        )
        self._set_text(
            self.queue_text,
            f"State: {value.state}\nCurrent path: {value.current_path}\n"
            f"Files: {value.files_completed}/{value.files_total}\n"
            f"Bytes: {format_bytes(value.bytes_completed)}/{format_bytes(value.bytes_total)}\n"
            f"Started: {value.started_at}\nElapsed: {value.elapsed_seconds:.1f} seconds",
        )

    def _finish_recovery(self, result):
        self.worker = None
        self.cancellation = None
        if self._closed:
            return
        active_serial,self._active_serial=self._active_serial,""
        if active_serial != self.serial:
            self._set_text(
                self.results_text,
                "A stale recovery result was ignored after the selected serial changed.",
            )
            self._sync_actions()
            return
        self.result = result
        recovered = sum(item.state in {"recovered", "resumed"} for item in result.items)
        skipped = sum(item.state == "skipped" for item in result.items)
        failed = sum(item.state == "failed" for item in result.items)
        state = "Interrupted" if result.interrupted else "Cancelled" if result.cancelled else "Partial Success" if result.partial_success else "Complete" if result.ok else "Failed"
        lines = [
            f"Result: {state}",
            f"Recovered: {recovered}",
            f"Skipped: {skipped}",
            f"Failed: {failed}",
            f"Manifest: {result.manifest_path or 'Not created'}",
        ]
        if result.error:
            lines.extend(("", result.error))
        lines.extend(
            ("", "Per-item results:", *(
                f"{item.state.upper():10} {item.source}"
                + (f" — {item.error}" if item.error else "")
                for item in result.items
            ))
        )
        self._set_text(self.results_text, "\n".join(lines))
        self.tabs.set("Results")
        self.header_values["queue"].configure(text=state)
        self.progress.set(1 if result.ok else 0)
        self._sync_actions()

    def cancel_recovery(self, interrupted=False):
        if self.cancellation:
            self.cancellation.cancel()
        if interrupted:
            self.header_values["queue"].configure(text="Interrupted — same serial required")
            self.current_path.configure(text="Device selection changed; queue is stopping safely.")

    def cleanup(self):
        self._closed = True
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        if self.cancellation:
            self.cancellation.cancel()
        worker = self.worker
        if worker is not None:
            worker.join(1)
        self.worker = None
