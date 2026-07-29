"""Lazy host-owned Plugin Project Wizard v1."""
from __future__ import annotations

import gc
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.gui.customtkinter_compat import (
    PendingCallbackOwner,
    ScopedScrollRouter,
    safe_focus,
    widget_exists,
    widget_within,
)
from app.gui.read_only_text import ReadOnlyTextView
from app.plugins.plugin_capabilities import CAPABILITIES, HIGH_IMPACT
from app.plugins.plugin_interactive import PLUGIN_NAVIGATION_DESTINATIONS
from app.plugins.plugin_project import (
    PluginProjectCapabilityPlan,
    PluginProjectContributionSpec,
    PluginProjectIdentity,
)
from app.plugins.plugin_project_wizard import capability_rows


class WizardViewport(ctk.CTkFrame):
    """One scoped vertical viewport; no permanent process-global binding."""

    def __init__(self, parent, theme, input_owner):
        super().__init__(
            parent, fg_color=theme["panel"], border_width=1,
            border_color=theme["border"],
        )
        self.theme = theme
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self, background=theme["panel"], highlightthickness=0,
            borderwidth=0, takefocus=True, yscrollincrement=1,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ctk.CTkScrollbar(
            self, width=18, command=self.canvas.yview,
            fg_color=theme["panel"], button_color=theme["gold_dark"],
            button_hover_color=theme["red_hover"],
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 2), pady=2)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ctk.CTkFrame(
            self.canvas, fg_color=theme["panel"], corner_radius=0
        )
        self.content.grid_columnconfigure(0, weight=1)
        self.window_id = self.canvas.create_window(
            0, 0, window=self.content, anchor="nw"
        )
        self.router = ScopedScrollRouter(
            self, self.canvas, owner=input_owner, scroll_units=42,
        )
        self.bindings = self.router.bindings
        self.canvas.bind("<Configure>", self._canvas_changed, add="+")
        self.content.bind("<Configure>", self._content_changed, add="+")

    def _inside(self, widget):
        return (
            widget in {self.canvas, self.scrollbar}
            or widget_within(widget, self.content)
        )

    def _wheel(self, event):
        return self.router._wheel(event)

    def _key(self, event):
        return self.router._key(event)

    def _canvas_changed(self, event):
        self.canvas.itemconfigure(self.window_id, width=max(1, event.width))
        self._sync()

    def _content_changed(self, _event=None):
        self._sync()

    def _sync(self):
        if widget_exists(self.canvas):
            self.canvas.configure(
                scrollregion=self.canvas.bbox("all") or (0, 0, 1, 1)
            )

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)

    def close(self):
        self.router.close()


class PluginProjectWizardWindow(ctk.CTkToplevel):
    STEPS = (
        "Project Type", "Identity", "Contribution", "Capabilities",
        "Developer Details", "Review", "Generate",
    )

    def __init__(
        self, parent, theme, controller, *, start_background, ui_dispatch,
        mode_provider, workbench_callback, help_callback=None, on_close=None,
        choose_folder=None, save_zip=None, save_brief=None, confirm=None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.theme = theme
        self.controller = controller
        self.start_background = start_background
        self.ui_dispatch = ui_dispatch
        self.mode_provider = mode_provider
        self.workbench_callback = workbench_callback
        self.help_callback = help_callback or (lambda _topic: None)
        self.on_close = on_close
        self.choose_folder = choose_folder or (
            lambda: filedialog.askdirectory(
                parent=self, title="Choose Project Parent Folder"
            )
        )
        self.save_zip = save_zip or (
            lambda **options: filedialog.asksaveasfilename(parent=self, **options)
        )
        self.save_brief = save_brief or (
            lambda **options: filedialog.asksaveasfilename(parent=self, **options)
        )
        self.confirm = confirm or (
            lambda title, text: messagebox.askyesno(title, text, parent=self)
        )
        self.current_step = 0
        self.page_widgets = {}
        self.capability_vars = {}
        self.worker = None
        self.generation = 0
        self._closed = False
        self.callbacks = PendingCallbackOwner(self)
        self.title(f"{METADATA.application_name} — Plugin Project Wizard")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 680)
        self.geometry(self._center(1180, 800))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.render()
        self.after_idle(self.focus_window)

    def _center(self, width, height):
        width = min(max(900, width), self.winfo_screenwidth())
        height = min(max(680, height), self.winfo_screenheight())
        return (
            f"{width}x{height}+{max(0, (self.winfo_screenwidth()-width)//2)}"
            f"+{max(0, (self.winfo_screenheight()-height)//2)}"
        )

    def _button(self, parent, text, command, *, primary=False, width=130):
        return ctk.CTkButton(
            parent, text=text, command=command, width=width,
            fg_color=self.theme["red"] if primary else self.theme["panel_alt"],
            hover_color=self.theme["red_hover"] if primary else self.theme["gold_dark"],
            border_width=1, border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )

    def _build(self):
        header = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 5))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            header, text="PLUGIN PROJECT WIZARD",
            font=("Times New Roman", 25, "bold"),
            text_color=self.theme["gold"], anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 1))
        self.mode_label = ctk.CTkLabel(
            header, text="", text_color=self.theme["muted"], anchor="w"
        )
        self.mode_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 7))
        self._button(
            header, "New Project", self.new_project, width=110
        ).grid(row=0, column=1, rowspan=2, padx=4)
        self._button(
            header, "Help", lambda: self.help_callback("plugin-project-wizard"),
            width=80,
        ).grid(row=0, column=2, rowspan=2, padx=(4, 10))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.steps = ctk.CTkFrame(
            body, width=205, fg_color=self.theme["panel_alt"],
            border_width=1, border_color=self.theme["border"],
        )
        self.steps.grid(row=0, column=0, sticky="ns", padx=(0, 6))
        self.steps.grid_propagate(False)
        self.step_labels = []
        for index, name in enumerate(self.STEPS):
            label = ctk.CTkLabel(
                self.steps, text=f"{index+1}. {name}", anchor="w",
                text_color=self.theme["muted"], height=38,
            )
            label.grid(row=index, column=0, sticky="ew", padx=10, pady=3)
            self.step_labels.append(label)
        self.viewport = WizardViewport(body, self.theme, self)
        self.viewport.grid(row=0, column=1, sticky="nsew")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 12))
        footer.grid_columnconfigure(1, weight=1)
        self.back_button = self._button(footer, "Back", self.back)
        self.back_button.grid(row=0, column=0, padx=3)
        self.status = ctk.CTkLabel(
            footer, text="", text_color=self.theme["muted"],
            anchor="w", wraplength=650,
        )
        self.status.grid(row=0, column=1, sticky="ew", padx=10)
        self.continue_button = self._button(
            footer, "Continue", self.continue_step, primary=True
        )
        self.continue_button.grid(row=0, column=2, padx=3)
        self.close_button = self._button(footer, "Close", self.close)
        self.close_button.grid(row=0, column=3, padx=3)

    def render(self):
        self.page_widgets = {}
        self.viewport.clear()
        for index, label in enumerate(self.step_labels):
            label.configure(
                text_color=(
                    self.theme["gold"] if index == self.current_step
                    else self.theme["muted"]
                ),
                fg_color=(
                    self.theme["red"] if index == self.current_step
                    else "transparent"
                ),
            )
        self.mode_label.configure(
            text=(
                f"{self.mode_provider().title()} mode · Runtime-only draft · "
                "Nothing is installed or executed"
            )
        )
        self.status.configure(text="")
        renderers = (
            self._project_type, self._identity, self._contribution,
            self._capabilities, self._developer, self._review, self._generate,
        )
        renderers[self.current_step]()
        self.back_button.configure(
            state="disabled" if self.current_step == 0 else "normal"
        )
        if self.current_step == len(self.STEPS) - 1:
            self.continue_button.grid_remove()
        else:
            self.continue_button.grid()
            self.continue_button.configure(
                text="Generate Options" if self.current_step == 5 else "Continue",
                state=(
                    "normal"
                    if self.current_step != 5 or self.controller.validated
                    else "disabled"
                ),
            )
        self.viewport._sync()

    def _heading(self, title, explanation):
        parent = self.viewport.content
        ctk.CTkLabel(
            parent, text=title.upper(), text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 3))
        ctk.CTkLabel(
            parent, text=explanation, text_color=self.theme["text"],
            anchor="w", justify="left", wraplength=800,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.error_label = ctk.CTkLabel(
            parent, text="", text_color=self.theme["error"],
            anchor="w", justify="left", wraplength=800,
        )
        self.error_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 5))
        self._next_row = 3

    def _label(self, text, row=None):
        row = self._next_row if row is None else row
        ctk.CTkLabel(
            self.viewport.content, text=text, text_color=self.theme["text"],
            anchor="w",
        ).grid(row=row, column=0, sticky="ew", padx=16, pady=(5, 1))
        return row

    def _entry(self, label, attribute, *, setter=None):
        row = self._label(label)
        value = getattr(self.controller.draft, attribute)
        widget = ctk.CTkEntry(
            self.viewport.content, fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"], text_color=self.theme["text"],
        )
        widget.insert(0, str(value))
        widget.grid(row=row + 1, column=0, sticky="ew", padx=16, pady=(0, 4))
        previous_value = [str(value)]
        def changed(_event=None):
            current = widget.get()
            if current == previous_value[0]:
                return
            previous_value[0] = current
            if setter:
                setter(current)
            else:
                setattr(self.controller.draft, attribute, current)
                self.controller._invalidate()
            self._bounded_error()
        widget.bind("<KeyRelease>", changed, add="+")
        widget.bind("<FocusOut>", changed, add="+")
        self.page_widgets[attribute] = widget
        self._next_row = row + 2
        return widget

    def _combo(self, label, attribute, values):
        row = self._label(label)
        widget = ctk.CTkComboBox(
            self.viewport.content, values=tuple(values),
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            button_color=self.theme["gold_dark"],
            button_hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
            command=lambda value: self._set_value(attribute, value),
        )
        widget.set(str(getattr(self.controller.draft, attribute)))
        widget.grid(row=row + 1, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.page_widgets[attribute] = widget
        self._next_row = row + 2
        return widget

    def _set_value(self, attribute, value):
        setattr(self.controller.draft, attribute, value)
        self.controller._invalidate()
        self._bounded_error()

    def _project_type(self):
        self._heading(
            "Interactive Plugin API 1.1 Window",
            "Creates a starter project, not a finished operational module. "
            "Generated actions are inert and require explicit clicks.",
        )
        card = ctk.CTkFrame(
            self.viewport.content, fg_color=self.theme["panel_alt"],
            border_width=1, border_color=self.theme["gold_dark"],
        )
        card.grid(row=3, column=0, sticky="ew", padx=16, pady=8)
        ctk.CTkLabel(
            card, text="RECOMMENDED · ZERO-CAPABILITY STARTER",
            text_color=self.theme["gold"], font=self.theme["header_font"],
        ).pack(anchor="w", padx=12, pady=(10, 3))
        ctk.CTkLabel(
            card,
            text=(
                "One host-owned window, informational view, bounded form, "
                "explicit no-op validation, and safe navigation example."
            ),
            text_color=self.theme["text"], justify="left", wraplength=740,
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _identity(self):
        self._heading(
            "Project Identity",
            "Choose stable derivative-owned identifiers. Suggestions are editable "
            "and do not claim global uniqueness.",
        )
        self._entry("Project display name", "project_name")
        self._entry("Author / publisher", "author")
        self._entry(
            "Plugin ID", "plugin_id", setter=self.controller.set_plugin_id
        )
        row = self._next_row
        self._button(
            self.viewport.content, "Suggest Plugin ID",
            self._suggest_plugin_id, width=170,
        ).grid(row=row, column=0, sticky="w", padx=16, pady=4)
        self._next_row += 1
        self._entry("Semantic version", "version")
        self._entry("Concise description", "description")
        self._entry("License", "license")
        row = self._label("Supported platforms")
        platform = ctk.CTkComboBox(
            self.viewport.content,
            values=("linux, windows", "linux", "windows"),
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            button_color=self.theme["gold_dark"],
            button_hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
            command=self._platform_changed,
        )
        platform.set(", ".join(self.controller.draft.platforms))
        platform.grid(row=row + 1, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.page_widgets["platforms"] = platform
        self._next_row = row + 2
        self._entry(
            "Portable project folder name", "folder_name",
            setter=self.controller.set_folder_name,
        )
        row = self._next_row
        self._button(
            self.viewport.content, "Suggest Folder Name",
            self._suggest_folder, width=180,
        ).grid(row=row, column=0, sticky="w", padx=16, pady=(4, 12))
        self._next_row += 1
        if self.mode_provider() == "advanced":
            self._label(
                "Exact constraints: lowercase plugin ID; semantic version; "
                "portable single folder component; `susadb.*` is reserved."
            )

    def _platform_changed(self, value):
        self.controller.draft.platforms = tuple(
            part.strip() for part in value.split(",") if part.strip()
        )
        self.controller._invalidate()

    def _suggest_plugin_id(self):
        for attribute in ("project_name", "author"):
            widget = self.page_widgets.get(attribute)
            if widget:
                setattr(self.controller.draft, attribute, widget.get())
        preview = self.controller.preview_plugin_id_suggestion()
        if preview.requires_confirmation and not self.confirm(
            "Replace Plugin ID Suggestion",
            "Current Plugin ID:\n"
            f"{preview.current}\n\nSuggested Plugin ID:\n"
            f"{preview.suggested}\n\nApply the suggested ID?",
        ):
            self.status.configure(
                text="Current Plugin ID retained.",
                text_color=self.theme["muted"],
            )
            return False
        value = self.controller.apply_plugin_id_suggestion(confirmed=True)
        widget = self.page_widgets["plugin_id"]
        widget.delete(0, "end")
        widget.insert(0, value)
        self.status.configure(
            text="Editable suggestion applied; global uniqueness is not claimed."
        )
        return True

    def _suggest_folder(self):
        preview = self.controller.preview_folder_suggestion()
        if preview.requires_confirmation and not self.confirm(
            "Replace Project Folder Suggestion",
            "Current project folder:\n"
            f"{preview.current}\n\nSuggested project folder:\n"
            f"{preview.suggested}\n\nApply the suggested folder name?",
        ):
            self.status.configure(
                text="Custom project folder retained.",
                text_color=self.theme["muted"],
            )
            return False
        value = self.controller.apply_folder_suggestion(confirmed=True)
        widget = self.page_widgets["folder_name"]
        widget.delete(0, "end")
        widget.insert(0, value)
        self.status.configure(
            text="Editable folder suggestion applied.",
            text_color=self.theme["muted"],
        )
        return True

    def _contribution(self):
        self._heading(
            "Window Contribution",
            "Wizard v1 generates one canonical interactive Pentest panel. "
            "The host owns its window, geometry, theme, and cleanup.",
        )
        self._entry("Contribution title", "contribution_title")
        self._entry(
            "Contribution ID", "contribution_id",
            setter=lambda value: self.controller.set_contribution_id(
                value, manual=True
            ),
        )
        self._combo(
            "Contribution type", "contribution_type", ("pentest-panel",)
        )
        self._combo("UI mode", "ui_mode", ("window", "hybrid"))
        row = self._next_row
        singleton = tk.BooleanVar(value=self.controller.draft.singleton)
        ctk.CTkCheckBox(
            self.viewport.content, text="Singleton window",
            variable=singleton, fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"],
            border_color=self.theme["gold_dark"],
            command=lambda: self._set_value("singleton", singleton.get()),
        ).grid(row=row, column=0, sticky="w", padx=16, pady=7)
        self.page_widgets["singleton"] = singleton
        self._next_row += 1
        for label, attribute in (
            ("Default width", "default_width"),
            ("Default height", "default_height"),
            ("Minimum width", "minimum_width"),
            ("Minimum height", "minimum_height"),
        ):
            self._entry(label, attribute)
        self._entry("Optional icon text", "icon")
        draft = self.controller.draft
        self.relationship = ctk.CTkLabel(
            self.viewport.content,
            text=(
                f"Manifest contribution ID: {draft.contribution_id or 'not set'}\n"
                f"Python registration ID: {draft.contribution_id or 'not set'}"
            ),
            text_color=self.theme["gold"], anchor="w", justify="left",
        )
        self.relationship.grid(
            row=self._next_row, column=0, sticky="ew", padx=16, pady=10
        )

    def _capabilities(self):
        self._heading(
            "Capability Plan",
            "Default: no capabilities. Declaring a capability requests "
            "permission; it does not implement the operation.",
        )
        self._button(
            self.viewport.content, "Keep Zero-Capability Starter",
            self._zero_capabilities, width=230,
        ).grid(row=3, column=0, sticky="w", padx=16, pady=5)
        row = 4
        selected = set(self.controller.draft.capabilities)
        self.capability_vars = {}
        for details in capability_rows():
            variable = tk.BooleanVar(value=details["name"] in selected)
            self.capability_vars[details["name"]] = variable
            text = (
                f"{details['name']} · {details['impact']}\n"
                f"{details['purpose']} {details['approval']}"
            )
            if self.mode_provider() == "advanced":
                text += f"\nSDK façade: {details['facade']}"
            ctk.CTkCheckBox(
                self.viewport.content, text=text, variable=variable,
                command=self._capabilities_changed,
                fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
                border_color=self.theme["gold_dark"],
            ).grid(row=row, column=0, sticky="w", padx=16, pady=5)
            row += 1
        self.high_ack = tk.BooleanVar(
            value=self.controller.draft.high_impact_acknowledged
        )
        self.high_ack_widget = ctk.CTkCheckBox(
            self.viewport.content,
            text=(
                "I acknowledge that high-impact declarations require explicit "
                "review and do not create an implementation."
            ),
            variable=self.high_ack,
            command=self._high_ack_changed,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            border_color=self.theme["gold_dark"],
        )
        self.high_ack_widget.grid(
            row=row, column=0, sticky="w", padx=16, pady=(10, 16)
        )

    def _capabilities_changed(self):
        self.controller.set_capabilities(
            name for name, variable in self.capability_vars.items()
            if variable.get()
        )
        self._bounded_error()

    def _high_ack_changed(self):
        self.controller.draft.high_impact_acknowledged = self.high_ack.get()
        self.controller._invalidate()
        self._bounded_error()

    def _zero_capabilities(self):
        self.controller.clear_capabilities()
        for variable in self.capability_vars.values():
            variable.set(False)
        self.high_ack.set(False)
        self.status.configure(text="Zero-capability starter retained.")

    def _developer(self):
        self._heading(
            "Developer Details",
            "These bounded intent notes populate documentation only. Do not enter "
            "credentials, tokens, passwords, serials, or package history.",
        )
        for label, attribute in (
            ("Intended purpose", "intended_purpose"),
            ("Expected operator workflow", "operator_workflow"),
            ("Planned data inputs", "planned_inputs"),
            ("Expected result / output", "expected_output"),
            ("Cancellation needs", "cancellation_needs"),
            ("Implementation notes for another LLM", "implementation_notes"),
        ):
            self._entry(label, attribute)
        self._combo(
            "Safe navigation example", "navigation_destination",
            PLUGIN_NAVIGATION_DESTINATIONS,
        )

    def _review(self):
        self._heading(
            "Review Project",
            "Review is non-writing. Validate Project explicitly runs production "
            "validation and Workbench static analysis without importing code.",
        )
        try:
            plan = self.controller.plan()
        except (TypeError, ValueError) as exc:
            self.error_label.configure(text=str(exc))
            self.continue_button.configure(state="disabled")
            return
        spec = plan.spec
        custom_folder_note = (
            "Custom folder name retained by operator.\n"
            if self.controller.custom_folder_retained else ""
        )
        summary = (
            f"Project: {spec.identity.display_name}\n"
            f"Plugin ID: {spec.identity.plugin_id}\n"
            f"Contribution ID: {spec.contribution.contribution_id}\n"
            f"Project folder: {spec.identity.folder_name}\n"
            f"Starter ZIP: {spec.identity.plugin_id}-{spec.identity.version}.zip\n"
            f"{custom_folder_note}"
            "Plugin API: 1.1\n"
            f"Capabilities: {', '.join(spec.capabilities.requested) or 'None'}\n"
            f"Public imports: app.plugins and documented contribution declaration\n"
            "Lifecycle: generated inert; install/trust/approve/enable/load/open remain separate\n"
            "Static analysis cannot prove future edited code is safe.\n\n"
            "Files:\n" + "\n".join(f"  {value.path}" for value in plan.files)
        )
        self.review_summary_widget = self._text_preview(
            "Review summary and file tree", summary, 280
        )
        manifest = json.dumps(
            json.loads(plan.file("manifest.json").text), indent=2, sort_keys=True
        )
        self._text_preview("Manifest preview", manifest, 260)
        self.validate_button = self._button(
            self.viewport.content, "Validate Project",
            self.validate_project, primary=True, width=180,
        )
        self.validate_button.grid(
            row=self._next_row, column=0, sticky="w", padx=16, pady=10
        )
        self._next_row += 1
        self.validation_area = ctk.CTkFrame(
            self.viewport.content,
            fg_color="transparent",
        )
        self.validation_area.grid(
            row=self._next_row, column=0, sticky="ew", padx=16, pady=(0, 16)
        )
        self.validation_area.grid_columnconfigure(0, weight=1)
        self._render_validation_projection()

    def _text_preview(self, label, value, height):
        row = self._label(label)
        widget = ReadOnlyTextView(
            self.viewport.content, height=height,
            fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"],
            border_width=1, border_color=self.theme["gold_dark"], wrap="word",
        )
        widget.grid(row=row + 1, column=0, sticky="ew", padx=16, pady=(0, 6))
        widget.replace(value)
        self._next_row = row + 2
        return widget

    def _validation_text(self):
        validation = self.controller.validation
        if validation is None:
            return "Not validated. No Workbench analysis has run."
        if validation.ok:
            return (
                "Compatible starter project\n"
                "Static validation does not prove future edited code is safe."
            )
        return "Validation blocked:\n" + "\n".join(validation.errors)

    def _render_validation_projection(self):
        if not hasattr(self, "validation_area") or not widget_exists(
            self.validation_area
        ):
            return
        for child in self.validation_area.winfo_children():
            child.destroy()
        validation = self.controller.validation
        self.validation_label = ctk.CTkLabel(
            self.validation_area,
            text=self._validation_text(),
            text_color=(
                self.theme["success"]
                if self.controller.validated else (
                    self.theme["error"] if validation else self.theme["muted"]
                )
            ),
            anchor="w", justify="left", wraplength=780,
        )
        self.validation_label.grid(
            row=0, column=0, sticky="ew", pady=(0, 6)
        )
        self.advisory_widgets = []
        for row, advisory in enumerate(self.controller.advisories(), 1):
            card = ctk.CTkFrame(
                self.validation_area,
                fg_color=self.theme["panel_alt"],
                border_width=1,
                border_color=self.theme["gold_dark"],
            )
            card.grid(row=row, column=0, sticky="ew", pady=4)
            card.grid_columnconfigure(0, weight=1)
            title = advisory.title
            if self.mode_provider() == "advanced" and advisory.rule_ids:
                title += " · " + ", ".join(advisory.rule_ids)
            ctk.CTkLabel(
                card, text=title, text_color=self.theme["gold"],
                font=self.theme["header_font"], anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            detail = ctk.CTkLabel(
                card, text=advisory.detail, text_color=self.theme["text"],
                anchor="w", justify="left", wraplength=750,
            )
            detail.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
            self.advisory_widgets.append((card, detail))
        self.viewport._sync()

    def validate_project(self):
        if self.worker is not None:
            return False
        try:
            self.controller.plan()
        except (TypeError, ValueError) as exc:
            self.error_label.configure(text=str(exc))
            return False
        self.validate_button.configure(state="disabled")
        self.validation_label.configure(
            text="Validation running…", text_color=self.theme["gold"]
        )
        return self._start_work("validate", self.controller.validate)

    def _generate(self):
        self._heading(
            "Generate",
            "Every output is explicit. Generation never installs, trusts, "
            "approves, enables, loads, opens, or executes the addon.",
        )
        actions = (
            ("Create Project Folder", self.create_project, True),
            ("Build Starter ZIP", self.build_zip, False),
            ("Open Generated Project in Workbench", self.open_in_workbench, False),
            ("Export Developer Brief", self.export_brief, False),
        )
        row = 3
        for text, callback, primary in actions:
            self._button(
                self.viewport.content, text, callback,
                primary=primary, width=280,
            ).grid(row=row, column=0, sticky="w", padx=16, pady=5)
            row += 1
        plan = self.controller.review_plan
        preview = (
            f"Folder name: {plan.spec.identity.folder_name}\n"
            f"ZIP name: {plan.spec.identity.plugin_id}-{plan.spec.identity.version}.zip\n"
            "Destination paths are never remembered across application restart."
            if plan else "Return to Review and validate the project first."
        )
        ctk.CTkLabel(
            self.viewport.content, text=preview,
            text_color=self.theme["muted"], anchor="w", justify="left",
        ).grid(row=row, column=0, sticky="ew", padx=16, pady=12)

    def _bounded_error(self):
        if not hasattr(self, "error_label"):
            return
        try:
            self._validate_step(show=False)
        except (TypeError, ValueError) as exc:
            self.error_label.configure(text=str(exc)[:300])
        else:
            self.error_label.configure(text="")

    def _validate_step(self, *, show=True):
        draft = self.controller.draft
        if self.current_step == 1:
            PluginProjectIdentity(
                draft.project_name, draft.plugin_id, draft.version, draft.author,
                draft.description, draft.license, draft.platforms, "1.1",
                draft.folder_name,
            )
        elif self.current_step == 2:
            PluginProjectContributionSpec(
                draft.contribution_id,
                draft.contribution_title or draft.project_name,
                draft.contribution_type, draft.ui_mode, draft.singleton,
                int(draft.default_width), int(draft.default_height),
                int(draft.minimum_width), int(draft.minimum_height), draft.icon,
            )
            if not draft.contribution_id.startswith(draft.plugin_id + "."):
                raise ValueError(
                    "Contribution ID must be owned by the project plugin ID."
                )
        elif self.current_step == 3:
            PluginProjectCapabilityPlan(
                draft.capabilities, draft.capability_justifications,
                draft.high_impact_acknowledged,
            )
        elif self.current_step in {4, 5}:
            self.controller.spec()
        return True

    def continue_step(self):
        try:
            self._validate_step()
        except (TypeError, ValueError) as exc:
            self.error_label.configure(text=str(exc)[:300])
            return False
        if self.current_step == 5 and not self.controller.validated:
            self.error_label.configure(text="Validate Project before generation.")
            return False
        self.current_step = min(self.current_step + 1, len(self.STEPS) - 1)
        self.render()
        return True

    def back(self):
        if self.current_step:
            self.current_step -= 1
            self.render()
        return True

    def apply_mode(self):
        if not self._closed:
            self.render()

    def _start_work(self, label, callback):
        if self.worker is not None:
            return False
        # Rerendered CustomTkinter controls may leave cyclic font objects.
        # Finalize those Tk-owned objects on the UI thread before the worker
        # performs allocation-heavy parsing that could otherwise trigger GC.
        gc.collect()
        self.generation += 1
        generation = self.generation
        def work():
            try:
                return callback()
            except Exception as exc:
                return exc
        self.worker = self.start_background(
            work,
            lambda result: self.ui_dispatch(
                self._work_done, generation, label, result
            ),
        )
        return True

    def _work_done(self, generation, label, result):
        self.worker = None
        if self._closed or generation != self.generation:
            return
        if label == "validate":
            if isinstance(result, Exception):
                self.controller.validation = None
                if hasattr(self, "validation_label") and widget_exists(
                    self.validation_label
                ):
                    self.validation_label.configure(
                        text=f"Validation failed: {type(result).__name__}",
                        text_color=self.theme["error"],
                    )
            else:
                self._render_validation_projection()
            self.continue_button.configure(
                state="normal" if self.controller.validated else "disabled"
            )
            if hasattr(self, "validate_button"):
                self.validate_button.configure(state="normal")
            return
        ok = bool(getattr(result, "ok", False))
        self.status.configure(
            text=(
                f"{label.replace('-', ' ').title()} complete."
                if ok else getattr(result, "error", "") or f"{label} failed."
            ),
            text_color=self.theme["success"] if ok else self.theme["error"],
        )

    def create_project(self):
        parent = self.choose_folder()
        if not parent:
            return False
        plan = self.controller.review_plan
        if plan is None:
            return False
        destination = Path(parent).expanduser().resolve() / (
            plan.spec.identity.folder_name
        )
        overwrite = destination.exists()
        if overwrite and not self.confirm(
            "Overwrite Existing Project",
            f"Replace the existing project folder {destination.name}?",
        ):
            return False
        return self._start_work(
            "project-folder",
            lambda: self.controller.create_folder(parent, overwrite=overwrite),
        )

    def build_zip(self):
        plan = self.controller.review_plan
        if plan is None:
            return False
        destination = self.save_zip(
            title="Build Starter ZIP",
            initialfile=(
                f"{plan.spec.identity.plugin_id}-"
                f"{plan.spec.identity.version}.zip"
            ),
            defaultextension=".zip",
        )
        if not destination:
            return False
        overwrite = Path(destination).exists()
        if overwrite and not self.confirm(
            "Overwrite Starter ZIP", f"Replace {Path(destination).name}?"
        ):
            return False
        return self._start_work(
            "starter-zip",
            lambda: self.controller.build_zip(
                destination, overwrite=overwrite
            ),
        )

    def export_brief(self):
        plan = self.controller.review_plan
        if plan is None:
            return False
        destination = self.save_brief(
            title="Export Developer Brief",
            initialfile="DEVELOPER_BRIEF.md",
            defaultextension=".md",
        )
        if not destination:
            return False
        overwrite = Path(destination).exists()
        if overwrite and not self.confirm(
            "Overwrite Developer Brief", f"Replace {Path(destination).name}?"
        ):
            return False
        return self._start_work(
            "developer-brief",
            lambda: self.controller.export_brief(
                destination, overwrite=overwrite
            ),
        )

    def open_in_workbench(self):
        path = (
            self.controller.generated_folder or self.controller.generated_zip
        )
        if not path:
            self.status.configure(
                text="Create a project folder or ZIP before Workbench handoff.",
                text_color=self.theme["error"],
            )
            return False
        self.workbench_callback(path)
        self.status.configure(
            text="Opened in Plugin Developer Workbench for static analysis only.",
            text_color=self.theme["gold"],
        )
        return True

    def new_project(self):
        if self.controller.draft.meaningful and not self.confirm(
            "Start New Project",
            "Discard the current runtime-only draft and start again?",
        ):
            return False
        self.controller.reset()
        self.current_step = 0
        self.render()
        return True

    def focus_window(self):
        if not self._closed and self.winfo_exists():
            self.deiconify()
            self.lift()
            safe_focus(self.viewport.canvas)
        return self

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.generation += 1
        self.callbacks.cancel_all()
        self.viewport.close()
        self.destroy()
        if self.on_close:
            self.on_close()
