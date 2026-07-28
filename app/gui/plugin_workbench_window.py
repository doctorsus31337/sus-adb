"""Lazy host-owned Plugin Developer Workbench window."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.gui.customtkinter_compat import PendingCallbackOwner, safe_focus
from app.gui.read_only_text import ReadOnlyTextView
from app.plugins.plugin_workbench import (
    FindingSeverity,
    PluginWorkbenchAnalyzer,
    PluginWorkbenchSource,
    STATIC_LIMITATION,
)
from app.plugins.plugin_workbench_output import (
    PluginWorkbenchPackageBuilder,
    atomic_write_report,
    render_json_report,
    render_markdown_report,
)


class PluginWorkbenchWindow(ctk.CTkToplevel):
    SECTIONS = (
        "Overview", "Findings", "Manifest", "Capabilities", "SDK & Imports",
        "Contributions", "Files", "Update Comparison", "Package",
    )

    def __init__(
        self, parent, theme, analyzer_factory, *,
        start_background, install_callback, mode_provider,
        help_callback=None, on_close=None, width=1180, height=780,
        open_zip_dialog=None, open_folder_dialog=None, save_dialog=None,
        confirm=None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.theme = theme
        self.analyzer_factory = analyzer_factory
        self.start_background = start_background
        self.install_callback = install_callback
        self.mode_provider = mode_provider
        self.help_callback = help_callback or (lambda _topic: None)
        self.on_close = on_close
        self.open_zip_dialog = open_zip_dialog or (
            lambda: filedialog.askopenfilename(
                parent=self, title="Open Plugin ZIP",
                filetypes=(("Plugin ZIP", "*.zip"), ("All files", "*.*")),
            )
        )
        self.open_folder_dialog = open_folder_dialog or (
            lambda: filedialog.askdirectory(parent=self, title="Open Plugin Folder")
        )
        self.save_dialog = save_dialog or (
            lambda **options: filedialog.asksaveasfilename(parent=self, **options)
        )
        self.confirm = confirm or (
            lambda title, text: messagebox.askyesno(title, text, parent=self)
        )
        self.source = None
        self.snapshot = None
        self.analysis_generation = 0
        self.cancel_event = None
        self.analysis_worker = None
        self._closed = False
        self.callbacks = PendingCallbackOwner(self)
        self.builder = PluginWorkbenchPackageBuilder()
        self.title(f"{METADATA.application_name} — Plugin Developer Workbench")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 650)
        self.geometry(self._geometry(width, height))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after_idle(self.focus_window)

    def _geometry(self, width, height):
        width = min(max(900, width), self.winfo_screenwidth())
        height = min(max(650, height), self.winfo_screenheight())
        return (
            f"{width}x{height}+{max(0, (self.winfo_screenwidth()-width)//2)}"
            f"+{max(0, (self.winfo_screenheight()-height)//2)}"
        )

    def _button(self, parent, text, command, *, primary=False):
        return ctk.CTkButton(
            parent, text=text, command=command,
            fg_color=self.theme["red"] if primary else self.theme["panel_alt"],
            hover_color=self.theme["red_hover"] if primary else self.theme["gold_dark"],
            border_width=1, border_color=self.theme["gold_dark"],
            text_color=self.theme["text"], height=30,
        )

    def _build(self):
        header = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            header, text="PLUGIN DEVELOPER WORKBENCH",
            font=self.theme["header_font"], text_color=self.theme["gold"],
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 0))
        self.identity = ctk.CTkLabel(
            header, text="No candidate selected", text_color=self.theme["muted"],
            anchor="w", wraplength=850,
        )
        self.identity.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 7))
        self.status = ctk.CTkLabel(
            header, text="Idle", text_color=self.theme["gold"], anchor="e",
        )
        self.status.grid(row=0, column=1, rowspan=2, padx=10)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=10, pady=3)
        actions.grid_columnconfigure(7, weight=1)
        self.open_zip = self._button(actions, "Open Plugin ZIP", self.choose_zip)
        self.open_zip.grid(row=0, column=0, padx=3)
        self.open_folder = self._button(
            actions, "Open Plugin Folder", self.choose_folder
        )
        self.open_folder.grid(row=0, column=1, padx=3)
        self.refresh_button = self._button(
            actions, "Refresh Analysis", self.refresh_analysis, primary=True
        )
        self.refresh_button.grid(row=0, column=2, padx=3)
        self.cancel_button = self._button(
            actions, "Cancel Analysis", self.cancel_analysis
        )
        self.cancel_button.grid(row=0, column=3, padx=3)
        self.replace_button = self._button(
            actions, "Replace Candidate", self.choose_folder
        )
        self.replace_button.grid(row=0, column=4, padx=3)
        self.help_button = self._button(
            actions, "Help", lambda: self.help_callback("plugin-workbench")
        )
        self.help_button.grid(row=0, column=8, padx=3)

        self.tabs = ctk.CTkTabview(
            self, fg_color=self.theme["panel"],
            segmented_button_fg_color=self.theme["panel_alt"],
            segmented_button_selected_color=self.theme["red"],
            segmented_button_selected_hover_color=self.theme["red_hover"],
            segmented_button_unselected_color=self.theme["panel_alt"],
            segmented_button_unselected_hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        self.pages = {}
        self.views = {}
        for section in self.SECTIONS:
            page = self.tabs.add(section)
            page.configure(fg_color=self.theme["bg"])
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(1, weight=1)
            self.pages[section] = page
            if section == "Findings":
                self._build_findings(page)
            elif section == "Package":
                self._build_package(page)
            else:
                self.views[section] = self._textbox(page)
        self.footer = ctk.CTkLabel(
            self, text=STATIC_LIMITATION, text_color=self.theme["muted"],
            anchor="w", wraplength=1120,
        )
        self.footer.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 10))
        self._set_running(False)
        self.render()

    def _textbox(self, parent):
        widget = ReadOnlyTextView(
            parent, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], border_width=1,
            border_color=self.theme["border"], wrap="word",
        )
        widget.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        return widget

    def _build_findings(self, page):
        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=4)
        bar.grid_columnconfigure(2, weight=1)
        self.severity_filter = ctk.CTkComboBox(
            bar, values=("All", "error", "warning", "information"),
            command=lambda _value: self.render_findings(),
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            button_color=self.theme["gold_dark"],
            button_hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
        )
        self.severity_filter.set("All")
        self.severity_filter.grid(row=0, column=0, padx=3)
        self.category_filter = ctk.CTkComboBox(
            bar, values=("All",), command=lambda _value: self.render_findings(),
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            button_color=self.theme["gold_dark"],
            button_hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
        )
        self.category_filter.set("All")
        self.category_filter.grid(row=0, column=1, padx=3)
        self.finding_search = ctk.CTkEntry(
            bar, placeholder_text="Search findings",
            fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.finding_search.grid(row=0, column=2, sticky="ew", padx=3)
        self.finding_search.bind("<KeyRelease>", lambda _event: self.render_findings())
        self.views["Findings"] = self._textbox(page)

    def _build_package(self, page):
        controls = ctk.CTkFrame(page, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=4)
        for column, (text, callback, primary) in enumerate((
            ("Export Markdown", lambda: self.export_report("markdown"), False),
            ("Export JSON", lambda: self.export_report("json"), False),
            ("Build Plugin ZIP", self.build_zip, True),
            ("Review in Plugin Manager", self.review_in_manager, False),
        )):
            button = self._button(controls, text, callback, primary=primary)
            button.grid(row=0, column=column, padx=3)
            setattr(self, {
                "Export Markdown": "markdown_button",
                "Export JSON": "json_button",
                "Build Plugin ZIP": "build_button",
                "Review in Plugin Manager": "install_button",
            }[text], button)
        self.views["Package"] = self._textbox(page)

    def choose_zip(self):
        value = self.open_zip_dialog()
        if value:
            self.select_candidate(value)

    def choose_folder(self):
        value = self.open_folder_dialog()
        if value:
            self.select_candidate(value)

    def select_candidate(self, value):
        try:
            source = PluginWorkbenchSource.selected(value)
        except ValueError as exc:
            self.status.configure(text=str(exc), text_color=self.theme["error"])
            return False
        self.cancel_analysis()
        self.source = source
        self.snapshot = None
        self.identity.configure(text=f"{source.display_name} · {source.kind.value}")
        self.render()
        self.refresh_analysis()
        return True

    def refresh_analysis(self):
        if self.source is None or self.analysis_worker is not None:
            return False
        self.analysis_generation += 1
        generation = self.analysis_generation
        cancel = threading.Event()
        self.cancel_event = cancel
        source = self.source
        self._set_running(True)

        def work():
            try:
                return self.analyzer_factory(cancel.is_set).analyze(source)
            except RuntimeError as exc:
                return exc

        self.analysis_worker = self.start_background(
            work,
            lambda result: self.parent.call_on_ui(
                self._analysis_done, generation, source, result
            ),
        )
        return True

    def cancel_analysis(self):
        if self.cancel_event is not None:
            self.cancel_event.set()
            self.analysis_generation += 1
        self.cancel_event = None
        self._set_running(False)

    def _analysis_done(self, generation, source, result):
        self.analysis_worker = None
        if (
            self._closed or generation != self.analysis_generation
            or source is not self.source
        ):
            return
        self.cancel_event = None
        self._set_running(False)
        if isinstance(result, Exception):
            self.status.configure(text=str(result), text_color=self.theme["muted"])
            return
        self.snapshot = result
        self.status.configure(
            text=result.status.value,
            text_color=(
                self.theme["error"]
                if result.status.value == "Blocked" else self.theme["gold"]
            ),
        )
        manifest = result.manifest
        self.identity.configure(
            text=(
                f"{manifest.name} · {manifest.plugin_id} · v{manifest.version} · "
                f"{result.source_kind.value} · {result.package_digest[:12]}"
                if manifest else f"{result.source_name} · {result.source_kind.value}"
            )
        )
        self.render()

    def _set_running(self, running):
        self.cancel_button.grid() if running else self.cancel_button.grid_remove()
        self.refresh_button.configure(state="disabled" if running else "normal")
        self.status.configure(
            text="Analysis running…" if running else self.status.cget("text")
        )

    def _set_text(self, name, text):
        widget = self.views[name]
        widget.replace(text)

    def apply_mode(self):
        self.render()

    def render(self):
        if self.snapshot is None:
            text = (
                "Choose one local plugin project folder or ZIP archive.\n\n"
                "Opening the Workbench performs no scan. Selecting a candidate "
                "starts only bounded static inspection.\n\n" + STATIC_LIMITATION
            )
            for name in self.views:
                self._set_text(name, text if name == "Overview" else "No analysis.")
            self._update_actions()
            return
        snapshot = self.snapshot
        mode = self.mode_provider()
        manifest = snapshot.manifest
        counts = snapshot.counts
        digest = (
            snapshot.package_digest
            if mode == "advanced" else snapshot.package_digest[:12]
        )
        overview = [
            f"Status: {snapshot.status.value}",
            f"Candidate: {snapshot.source_name}",
            f"Digest: {digest or 'unavailable'}",
            f"Files: {len(snapshot.files)}",
            f"Bytes: {sum(item.size for item in snapshot.files)}",
            f"Errors: {counts['error']} · Warnings: {counts['warning']} · Information: {counts['information']}",
        ]
        if manifest:
            overview.extend((
                f"Plugin: {manifest.name}",
                f"ID: {manifest.plugin_id}" if mode == "advanced" else "",
                f"Version: {manifest.version}",
                f"Requested capabilities: {len(manifest.requested_capabilities)}",
                f"Contributions: {len(manifest.contributed_components)}",
            ))
        overview.append("\nRecommended next action: " + (
            "Resolve blocking findings." if snapshot.status.value == "Blocked"
            else "Review warnings and the Package plan."
        ))
        self._set_text("Overview", "\n".join(value for value in overview if value))
        self._set_text(
            "Manifest",
            json_text(snapshot.raw_manifest) if mode == "advanced"
            else self._guided_manifest(manifest),
        )
        self._set_text(
            "Capabilities",
            "\n".join(manifest.requested_capabilities) if manifest else "No valid manifest.",
        )
        sdk_lines = [
            f"Observed PluginAPI method: {value}"
            for value in snapshot.observed_api_methods
        ]
        sdk_lines.extend(
            self._format_finding(item, mode)
            for item in snapshot.findings
            if item.category in {"Public SDK", "Imports", "Python Syntax"}
        )
        self._set_text("SDK & Imports", "\n\n".join(sdk_lines) or "No SDK/import findings.")
        self._set_text(
            "Contributions",
            "\n".join(
                f"{item.contribution_id} · {item.contribution_type} · {item.factory or 'no factory'}"
                for item in (manifest.contributed_components if manifest else ())
            ) or "No contributions.",
        )
        self._set_text(
            "Files",
            "\n".join(
                f"{item.path} · {item.size} bytes"
                + (f" · EXCLUDED: {item.excluded_reason}" if item.excluded_reason else "")
                + (f" · {item.digest}" if mode == "advanced" else "")
                for item in snapshot.files
            ),
        )
        self._set_text("Update Comparison", self._comparison_text(mode))
        self._set_text("Package", self._package_text())
        categories = sorted({item.category for item in snapshot.findings})
        self.category_filter.configure(values=("All", *categories))
        if self.category_filter.get() not in {"All", *categories}:
            self.category_filter.set("All")
        self.render_findings()
        self._update_actions()

    @staticmethod
    def _guided_manifest(manifest):
        if manifest is None:
            return "No valid manifest."
        return (
            f"{manifest.name} version {manifest.version}\n"
            f"Plugin API {manifest.plugin_api_version}\n"
            f"{len(manifest.requested_capabilities)} requested capabilities\n"
            f"{len(manifest.contributed_components)} contributions"
        )

    def render_findings(self):
        if self.snapshot is None:
            self._set_text("Findings", "No analysis.")
            return
        severity = self.severity_filter.get()
        category = self.category_filter.get()
        query = self.finding_search.get().casefold().strip()
        values = [
            item for item in self.snapshot.findings
            if (severity == "All" or item.severity.value == severity)
            and (category == "All" or item.category == category)
            and (
                not query or query in " ".join((
                    item.title, item.category, item.explanation,
                    item.remediation, item.path, item.rule_id,
                )).casefold()
            )
        ]
        mode = self.mode_provider()
        self._set_text(
            "Findings",
            "\n\n".join(self._format_finding(item, mode) for item in values)
            or "No findings match the current filters.",
        )

    @staticmethod
    def _format_finding(item, mode):
        location = item.path
        if mode == "advanced" and location and item.line:
            location += f":{item.line}:{item.column}"
        prefix = f"[{item.severity.value.upper()}] "
        if mode == "advanced":
            prefix += f"{item.rule_id} · "
        return (
            f"{prefix}{item.title}\n"
            + (f"{location}\n" if location else "")
            + f"{item.explanation}\nRemediation: {item.remediation}"
        )

    def _comparison_text(self, mode):
        comparison = self.snapshot.comparison if self.snapshot else None
        if comparison is None:
            return "No installed package with this plugin ID was projected."
        digest = lambda value: value if mode == "advanced" else value[:12]
        return "\n".join((
            f"Installed version: {comparison.installed_version}",
            f"Candidate version: {comparison.candidate_version}",
            f"Installed digest: {digest(comparison.installed_digest)}",
            f"Candidate digest: {digest(comparison.candidate_digest)}",
            f"Same-version contents changed: {'Yes' if comparison.same_version_digest_changed else 'No'}",
            "Added files: " + ", ".join(comparison.added_files),
            "Removed files: " + ", ".join(comparison.removed_files),
            "Modified files: " + ", ".join(comparison.modified_files),
            "Capabilities added: " + ", ".join(comparison.capability_additions),
            "Capabilities removed: " + ", ".join(comparison.capability_removals),
            "Contributions added: " + ", ".join(comparison.contribution_additions),
            "Contributions removed: " + ", ".join(comparison.contribution_removals),
            "Contributions changed: " + ", ".join(comparison.contribution_changes),
        ))

    def _package_text(self):
        if self.source is None or self.snapshot is None:
            return "Analyze a candidate to preview packaging and reports."
        plan = self.builder.plan(self.source, self.snapshot)
        return "\n".join((
            f"Build allowed: {'Yes' if plan.allowed else 'No'}",
            f"Plugin Manager review: {self._handoff_reason()}",
            f"Included files: {len(plan.included)}",
            f"Excluded files: {len(plan.excluded)}",
            f"Total bytes: {plan.total_bytes}",
            f"Reason: {plan.reason}" if plan.reason else "",
            "",
            "Included:",
            *plan.included,
            "",
            "Excluded:",
            *(f"{path} · {reason}" for path, reason in plan.excluded),
        ))

    def _handoff_reason(self):
        if self.snapshot is None:
            return "Unavailable — analyze a candidate first."
        reserved = next(
            (item for item in self.snapshot.findings if item.rule_id == "COMP002"),
            None,
        )
        if reserved:
            return f"Unavailable — {reserved.remediation}"
        if self.snapshot.status.value == "Blocked":
            return "Unavailable — resolve blocking findings."
        return "Available — production validation will run again before disabled storage."

    def _update_actions(self):
        ready = self.snapshot is not None
        for button in (self.markdown_button, self.json_button):
            button.configure(state="normal" if ready else "disabled")
        plan = (
            self.builder.plan(self.source, self.snapshot)
            if ready and self.source is not None else None
        )
        self.build_button.configure(
            state="normal" if plan and plan.allowed else "disabled"
        )
        installable = ready and self.snapshot.status.value != "Blocked"
        self.install_button.configure(state="normal" if installable else "disabled")

    def export_report(self, kind):
        if self.snapshot is None:
            return False
        extension = ".md" if kind == "markdown" else ".json"
        filename = safe_stem(self.snapshot.source_name) + "-plugin-report" + extension
        destination = self.save_dialog(
            title=f"Export {kind.title()} Report",
            initialfile=filename,
            defaultextension=extension,
        )
        if not destination:
            return False
        overwrite = (
            not Path(destination).exists()
            or self.confirm("Overwrite Report", f"Replace {Path(destination).name}?")
        )
        content = (
            render_markdown_report(self.snapshot)
            if kind == "markdown" else render_json_report(self.snapshot)
        )
        result = atomic_write_report(destination, content, overwrite=overwrite)
        self.status.configure(
            text="Report exported." if result.ok else result.error,
            text_color=self.theme["gold"] if result.ok else self.theme["error"],
        )
        return result.ok

    def build_zip(self):
        if self.source is None or self.snapshot is None:
            return False
        plan = self.builder.plan(self.source, self.snapshot)
        if not plan.allowed:
            return False
        if any(
            item.severity is FindingSeverity.WARNING
            for item in self.snapshot.findings
        ) and not self.confirm(
            "Review Package Warnings",
            "Warnings remain. Build the deterministic ZIP after reviewing them?",
        ):
            return False
        destination = self.save_dialog(
            title="Build Plugin ZIP",
            initialfile=f"{safe_stem(plan.plugin_id)}-{plan.version}.zip",
            defaultextension=".zip",
        )
        if not destination:
            return False
        overwrite = (
            not Path(destination).exists()
            or self.confirm("Overwrite Plugin ZIP", f"Replace {Path(destination).name}?")
        )
        result = self.builder.build(
            self.source, self.snapshot, destination, overwrite=overwrite
        )
        self.status.configure(
            text=(
                f"ZIP built · SHA-256 {result.digest[:12]}"
                if result.ok else result.error
            ),
            text_color=self.theme["gold"] if result.ok else self.theme["error"],
        )
        return result.ok

    def review_in_manager(self):
        if self.source is None or self.snapshot is None:
            return False
        manifest = self.snapshot.manifest
        if manifest is None or self.snapshot.status.value == "Blocked":
            return False
        if not self.confirm(
            "Install Through Plugin Manager",
            f"Forward {manifest.name} {manifest.version} "
            f"({self.snapshot.package_digest[:12]}) to production validation "
            "and disabled storage?\n\nThis does not trust, approve, enable, load, or open it.",
        ):
            return False
        result = self.install_callback(self.source.path)
        self.status.configure(
            text=(
                "Stored disabled through Plugin Manager."
                if result.ok else result.error or "Installation failed."
            ),
            text_color=self.theme["gold"] if result.ok else self.theme["error"],
        )
        return result.ok

    def focus_window(self):
        if self.winfo_exists():
            self.deiconify()
            self.lift()
            safe_focus(self.open_zip if self.source is None else self.tabs)
        return self

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.cancel_analysis()
        self.callbacks.cancel_all()
        self.destroy()
        if self.on_close:
            self.on_close()


def safe_stem(value):
    stem = Path(value).stem
    cleaned = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in stem
    ).strip(".-")
    return cleaned or "plugin"


def json_text(value):
    return json.dumps(value, indent=2, sort_keys=True, default=str)
