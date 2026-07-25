"""Host-owned Instrumentation & Root Readiness Advisor workspace."""

from __future__ import annotations

import queue
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.core.instrumentation_readiness import (
    InstrumentationReadinessService,
    ReadinessActionResult,
)
from app.core.worker import BackgroundWorker


class InstrumentationReadinessPanel(ctk.CTkFrame):
    SECTIONS = (
        "Overview",
        "Device Identity",
        "Root & Boot Chain",
        "Frida Routes",
        "Frida Server Setup",
        "Gadget Readiness",
        "Firmware Inputs",
        "Compatibility",
        "Plan",
    )

    def __init__(
        self,
        parent,
        theme,
        service: InstrumentationReadinessService,
        *,
        open_apk_lab=None,
        help_callback=None,
        file_chooser=None,
        confirm=None,
        ui_dispatch=None,
    ):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme = theme
        self.service = service
        self.open_apk_lab = open_apk_lab
        self.help_callback = help_callback
        self.file_chooser = file_chooser or (
            lambda title: filedialog.askopenfilename(
                parent=self.winfo_toplevel(), title=title
            )
        )
        self.confirm = confirm or (
            lambda title, message: messagebox.askyesno(
                title, message, parent=self.winfo_toplevel()
            )
        )
        self._local_queue = None
        self._poll_id = None
        if ui_dispatch is None:
            self._local_queue = queue.Queue()
            self.dispatch = (
                lambda callback, *args: self._local_queue.put((callback, args))
            )
            self._poll_id = self.after(15, self._poll)
        else:
            self.dispatch = ui_dispatch
        self.context = None
        self.serial = ""
        self.adb_state = "unavailable"
        self.assessment = None
        self.validation = None
        self.busy = False
        self._workers = set()
        self._closed = False
        self.destination_value = InstrumentationReadinessService.DEFAULT_DESTINATION
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_tabs()
        self._render()

    def _poll(self):
        if self._closed or self._local_queue is None:
            return
        while True:
            try:
                callback, args = self._local_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self._poll_id = self.after(15, self._poll)

    def _build_header(self):
        header = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(4, 2))
        for column in range(6):
            header.grid_columnconfigure(column, weight=1)
        self.header_values = {}
        for column, (key, label) in enumerate((
            ("device", "Device"),
            ("serial", "Serial"),
            ("adb", "ADB State"),
            ("root", "Existing Root"),
            ("route", "Available Route"),
        )):
            cell = ctk.CTkFrame(header, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="ew", padx=6, pady=4)
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
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=5, sticky="e", padx=6, pady=4)
        self.scan_button = self._button(
            actions, "Scan Capabilities", self.scan_capabilities, 0
        )
        self._button(
            actions, "Help",
            lambda: self.help_callback("readiness-advisor")
            if self.help_callback else None,
            1,
        )
        self.warning = ctk.CTkLabel(
            header,
            text=(
                "Bootloader unlocking commonly wipes user data and must not "
                "be used as a recovery technique."
            ),
            text_color=self.theme["error"], anchor="w", wraplength=1050,
        )
        self.warning.grid(
            row=1, column=0, columnspan=6, sticky="ew", padx=7, pady=(2, 7)
        )

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["border"],
            segmented_button_fg_color=self.theme["panel_alt"],
            segmented_button_selected_color=self.theme["red"],
            segmented_button_selected_hover_color=self.theme["red_hover"],
            segmented_button_unselected_color=self.theme["panel_alt"],
            segmented_button_unselected_hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=5, pady=(2, 5))
        self.pages = {name: self.tabs.add(name) for name in self.SECTIONS}
        self.views = {}
        for name, page in self.pages.items():
            page.configure(fg_color=self.theme["bg"])
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(0, weight=1)
            if name == "Frida Server Setup":
                self._build_server_setup(page)
            elif name == "Gadget Readiness":
                self._build_gadget(page)
            elif name == "Firmware Inputs":
                self._build_firmware(page)
            else:
                self.views[name] = self._text(page)

    def _text(self, parent):
        text = ctk.CTkTextbox(
            parent, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], border_width=1,
            border_color=self.theme["border"], wrap="word",
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        text.configure(state="disabled")
        return text

    def _build_server_setup(self, page):
        page.grid_rowconfigure(2, weight=1)
        selected = ctk.CTkFrame(page, fg_color=self.theme["panel_alt"])
        selected.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        selected.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            selected, text="Local binary", text_color=self.theme["muted"]
        ).grid(row=0, column=0, padx=6, pady=5)
        self.binary_label = ctk.CTkLabel(
            selected, text="None selected", text_color=self.theme["gold"],
            anchor="w",
        )
        self.binary_label.grid(row=0, column=1, sticky="ew", padx=6)
        self._button(selected, "1. Select Binary", self.select_binary, 2)
        ctk.CTkLabel(
            selected, text="Destination", text_color=self.theme["muted"]
        ).grid(row=1, column=0, padx=6, pady=5)
        self.destination = ctk.CTkEntry(
            selected, fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"], text_color=self.theme["text"],
        )
        self.destination.grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        self.destination.insert(0, self.destination_value)
        self.destination.configure(state="readonly")

        controls = ctk.CTkFrame(page, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
        actions = (
            ("2. Validate", self.validate_selected),
            ("3. Preview Upload", self.preview_upload),
            ("4. Upload", lambda: self.run_server_action("upload")),
            ("5. Set Executable", lambda: self.run_server_action("chmod")),
            ("6. Start", lambda: self.run_server_action("start")),
            ("7. Managed Forwarding", lambda: self.run_server_action("forward")),
            ("8. Verify Version", lambda: self.run_server_action("version")),
            ("9. Verify Reachability", lambda: self.run_server_action("reach")),
            ("10. Stop", lambda: self.run_server_action("stop")),
            ("11. Remove Managed", lambda: self.run_server_action("remove")),
        )
        self.server_buttons = []
        for index, (label, command) in enumerate(actions):
            controls.grid_columnconfigure(index % 5, weight=1)
            button = self._button(
                controls, label, command, index % 5, row=index // 5
            )
            self.server_buttons.append(button)
        self.server_output = self._text(page)
        self.server_output.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)

    def _build_gadget(self, page):
        page.grid_rowconfigure(0, weight=1)
        body = ctk.CTkFrame(
            page, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["border"],
        )
        body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            body,
            text=(
                "Gadget preparation reuses APK Laboratory. Decode, Gadget "
                "injection, build, signing, installation, launch, and script "
                "load remain separate explicit operations."
            ),
            text_color=self.theme["text"], justify="left", anchor="w",
            wraplength=820,
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self._button(
            body, "Open APK Laboratory with Selected App",
            self.open_apk_lab or (lambda: None), 0, row=1,
        )

    def _build_firmware(self, page):
        page.grid_rowconfigure(1, weight=1)
        controls = ctk.CTkFrame(page, fg_color=self.theme["panel_alt"])
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            controls,
            text=(
                "Only a local operator-selected input is hashed. "
                "No download, patch, flash, or exploit search occurs."
            ),
            text_color=self.theme["text"], anchor="w", wraplength=760,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=7)
        self._button(
            controls, "Select Firmware Input", self.select_firmware, 1
        )
        self.firmware_output = self._text(page)
        self.firmware_output.grid(
            row=1, column=0, sticky="nsew", padx=8, pady=8
        )

    def _button(self, parent, text, command, column, row=0):
        button = ctk.CTkButton(
            parent, text=text, command=command,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        button.grid(row=row, column=column, sticky="ew", padx=3, pady=3)
        return button

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def apply_context(self, context):
        previous = self.serial
        self.context = context
        selected = getattr(context, "selected_device", {}) or {}
        self.serial = selected.get("serial", "")
        self.adb_state = selected.get(
            "state", getattr(context, "adb_state", "unavailable")
        )
        if previous and previous != self.serial:
            self.assessment = None
            self.validation = None
        self._render()

    def _render(self):
        selected = (
            getattr(self.context, "selected_device", {}) or {}
            if self.context else {}
        )
        self.header_values["device"].configure(
            text=selected.get("display_name") or self.serial or "None"
        )
        self.header_values["serial"].configure(text=self.serial or "None")
        self.header_values["adb"].configure(text=self.adb_state.title())
        self.header_values["root"].configure(
            text=(
                "Yes" if self.assessment and self.assessment.root_required
                and self.assessment.route.value.startswith("ROOTED")
                else "Unknown" if self.assessment is None
                else "No"
            )
        )
        self.header_values["route"].configure(
            text=self.assessment.route.value if self.assessment else "Scan required"
        )
        self.scan_button.configure(
            state=(
                "normal"
                if not self.busy and self.serial
                and self.adb_state in {"device", "recovery", "sideload"}
                else "disabled"
            )
        )
        placeholder = (
            "Select an authorized device and choose Scan Capabilities. "
            "No route action runs automatically."
        )
        if self.assessment:
            route = self.assessment
            report = "\n".join((
                f"Route: {route.route.value}",
                "",
                "Supporting evidence:",
                *(f"• {value}" for value in route.evidence),
                "",
                "Prerequisites:",
                *(f"• {value}" for value in route.prerequisites or ("None",)),
                "",
                "Blockers:",
                *(f"• {value}" for value in route.blockers or ("None",)),
                "",
                "Warnings:",
                *(f"• {value}" for value in route.warnings or ("None",)),
                "",
                f"Next action: {route.next_action}",
                f"Root required: {'Yes' if route.root_required else 'No'}",
                "Device modification required: "
                f"{'Yes' if route.device_modification_required else 'No'}",
                "APK modification required: "
                f"{'Yes' if route.apk_modification_required else 'No'}",
                f"Data-loss risk: {route.data_loss_risk}",
            ))
        else:
            report = placeholder
        identity = (
            f"Device: {selected.get('display_name') or 'Unknown'}\n"
            f"Serial: {self.serial or 'None'}\n"
            f"ADB state: {self.adb_state}\n"
            f"Architecture: "
            f"{getattr(self.assessment, 'architecture', '') or 'Unknown'}"
        )
        values = {
            "Overview": report,
            "Device Identity": identity,
            "Root & Boot Chain": (
                report + "\n\nThis view advises only. It never unlocks, "
                "flashes, patches boot images, wipes, or changes verified boot."
            ),
            "Frida Routes": report,
            "Compatibility": report,
            "Plan": (
                report + "\n\nReview each next action. Opening this plan does "
                "not upload, start Frida, patch an APK, install, attach, or spawn."
            ),
        }
        for name, text in values.items():
            self._set_text(self.views[name], text)
        enabled = (
            not self.busy and self.assessment is not None
            and self.assessment.route.value in {
                "ROOTED_SERVER_READY", "ROOTED_SERVER_SETUP_AVAILABLE"
            }
        )
        for button in getattr(self, "server_buttons", ()):
            button.configure(state="normal" if enabled else "disabled")

    def select_firmware(self):
        path = self.file_chooser("Select local firmware input")
        if not path:
            return
        self._run(
            "Inspect Firmware Input",
            lambda: self.service.inspect_firmware_input(path),
            self._show_firmware,
        )

    def _show_firmware(self, result):
        self._set_text(
            self.firmware_output,
            "\n".join((
                f"Path: {result.path}",
                f"Size: {result.size}",
                f"SHA-256: {result.sha256 or 'Unavailable'}",
                f"Classification: {result.classification}",
                *(f"Warning: {value}" for value in result.warnings),
                "",
                "This result is advisory. No flash or modification action is available.",
            )),
        )
        self.tabs.set("Firmware Inputs")

    def scan_capabilities(self):
        serial, state = self.serial, self.adb_state
        self._run(
            "Scan Device Capabilities",
            lambda: self.service.assess_device(serial, state),
            lambda value: self._apply_assessment(serial, value),
        )

    def _apply_assessment(self, serial, assessment):
        if serial != self.serial:
            self._show_error("Selected device changed; stale readiness was ignored.")
            return
        self.assessment = assessment
        self._render()
        self.tabs.set("Frida Routes")

    def select_binary(self):
        path = self.file_chooser("Select local Frida Server binary")
        if not path:
            return
        self.validation = None
        self.binary_label.configure(text=path)
        self._set_text(
            self.server_output,
            "Binary selected. Choose Validate; no upload has occurred.",
        )

    def validate_selected(self):
        path = self.binary_label.cget("text")
        if not path or path == "None selected":
            self._show_error("Select a local Frida Server binary first.")
            return
        architecture = getattr(self.assessment, "architecture", "")
        self.validation = self.service.validate_binary(path, architecture)
        validation = self.validation
        self._set_text(
            self.server_output,
            "\n".join((
                f"Valid: {'Yes' if validation.valid else 'No'}",
                f"Path: {validation.path}",
                f"Size: {validation.size}",
                f"SHA-256: {validation.sha256 or 'Unavailable'}",
                f"Binary architecture: {validation.architecture or 'Unknown'}",
                f"Device architecture: {validation.device_architecture or 'Unknown'}",
                *(f"Error: {error}" for error in validation.errors),
            )),
        )

    def preview_upload(self):
        if self.validation is None:
            self._show_error("Validate the selected binary first.")
            return
        self._show_result(
            self.service.preview_upload(
                self.validation, self.destination.get()
            )
        )

    def run_server_action(self, action):
        serial = self.serial
        destination = self.destination.get()
        changing = action not in {"version", "reach"}
        if changing and not self.confirm(
            f"Confirm {action}",
            f"Run only this {action} step on serial {serial}?\n\n"
            "No later step will run automatically.",
        ):
            return
        operations = {
            "upload": lambda: self.service.upload(
                serial, self.validation, destination, confirmed=True
            ) if self.validation else ReadinessActionResult(
                False, "Upload", serial, error="Validate a binary first."
            ),
            "chmod": lambda: self.service.set_executable(
                serial, destination, confirmed=True
            ),
            "start": lambda: self.service.start(
                serial, destination, confirmed=True
            ),
            "forward": lambda: self.service.configure_forwarding(
                serial, confirmed=True
            ),
            "version": lambda: self.service.verify_version(serial, destination),
            "reach": lambda: self.service.verify_reachability(serial),
            "stop": lambda: self.service.stop(serial, confirmed=True),
            "remove": lambda: self.service.remove_managed(
                serial, destination, confirmed=True
            ),
        }
        self._run(action.title(), operations[action], self._show_result)

    def _show_result(self, result: ReadinessActionResult):
        lines = [
            f"Action: {result.action}",
            f"Serial: {result.serial or self.serial or 'None'}",
            f"Result: {'Success' if result.ok else 'Blocked/Failed'}",
        ]
        if result.preview:
            lines.extend(("", "Preview:", *result.preview))
        for command_result in result.results:
            lines.extend((
                "",
                f"Command argv: {command_result.command}",
                command_result.output or "Complete.",
            ))
        if result.error:
            lines.extend(("", f"Error: {result.error}"))
        self._set_text(self.server_output, "\n".join(lines))
        self.tabs.set("Frida Server Setup")

    def _show_error(self, message):
        self._set_text(self.server_output, f"Blocked/Failed\n\n{message}")
        self.tabs.set("Frida Server Setup")

    def _run(self, title, operation, callback):
        if self.busy:
            return
        self.busy = True
        self._render()
        worker = None

        def target():
            try:
                return True, operation()
            except Exception as exc:
                return False, exc

        def finished(outcome):
            self.dispatch(self._finish, worker, title, outcome, callback)

        worker = BackgroundWorker(target, callback=finished)
        self._workers.add(worker)
        worker.start()

    def _finish(self, worker, title, outcome, callback):
        self._workers.discard(worker)
        if self._closed:
            return
        self.busy = False
        self._render()
        ok, value = outcome
        if not ok:
            self._show_error(f"{title}: {value}")
            return
        callback(value)

    def cleanup(self):
        self._closed = True
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        for worker in tuple(self._workers):
            worker.join(1)
