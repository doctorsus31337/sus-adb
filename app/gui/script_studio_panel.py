"""Responsive Gothic Script Studio workspace."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from app.core.device import Device
from app.core.frida_runtime_manager import FridaRuntimeManager, RuntimeResult
from app.core.frida_target import FridaTarget
from app.core.script_descriptor import ScriptDescriptor, ScriptKind, TrustState
from app.core.script_event import ScriptEvent
from app.core.script_library import ScriptLibrary
from app.core.script_profile import FailurePolicy, ScriptProfile, ScriptStage
from app.core.script_profile_runner import ScriptProfileRunner
from app.core.script_validator import ScriptValidator
from app.core.worker import BackgroundWorker


class ScriptStudioPanel(ctk.CTkFrame):
    def __init__(self, parent, theme, library: ScriptLibrary, runtime: FridaRuntimeManager, validator: ScriptValidator, log_callback, confirm_callback=None, objection_recipes=None):
        super().__init__(parent, fg_color=theme["bg"], corner_radius=0)
        self.theme, self.library, self.runtime, self.validator, self.log = theme, library, runtime, validator, log_callback
        self.confirm = confirm_callback or (lambda title, text: messagebox.askyesno(title, text, parent=self.winfo_toplevel()))
        self.objection_recipes = objection_recipes
        self.prepared_recipe = None
        self.device: Device | None = None; self.target: FridaTarget | None = None
        self.descriptors: tuple[ScriptDescriptor, ...] = (); self.selected: ScriptDescriptor | None = None
        self.events: list[ScriptEvent] = []; self.display_paused = False; self.editor_dirty = False
        self.profiles: list[ScriptProfile] = []; self.selected_profile: ScriptProfile | None = None
        self.profile_runner = ScriptProfileRunner(runtime, self.queue_event)
        self.runtime.event_callback = self.queue_event
        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(0, weight=1)
        self._build_header(); self._build_workspace(); self._build_library(); self._build_editor(); self._build_runtime(); self._build_messages(); self._build_profiles()
        self.refresh_library(); self._sync_header(); self._update_actions()

    def _button(self, parent, text, command, row=0, column=0):
        button = ctk.CTkButton(parent, text=text, command=command, fg_color=self.theme["red"], hover_color=self.theme["red_hover"], text_color=self.theme["text"], border_width=1, border_color=self.theme["gold_dark"], height=30)
        button.grid(row=row, column=column, sticky="ew", padx=3, pady=3); return button

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=self.theme["panel"], border_width=1, border_color=self.theme["gold_dark"], corner_radius=9)
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(5, 3))
        for index in range(7): header.grid_columnconfigure(index, weight=1)
        self.header_labels = {}
        for index, (key, title) in enumerate((("device", "Device"), ("target", "Target"), ("runtime", "Runtime"), ("python", "Python Frida"), ("server", "Server"), ("versions", "Versions"), ("loaded", "Loaded"))):
            cell = ctk.CTkFrame(header, fg_color="transparent"); cell.grid(row=0, column=index, sticky="ew", padx=4, pady=5)
            ctk.CTkLabel(cell, text=title, text_color=self.theme["muted"], font=("Segoe UI", 10, "bold")).pack()
            label = ctk.CTkLabel(cell, text="Unknown", text_color=self.theme["gold"], font=("Consolas", 10, "bold"), wraplength=120); label.pack(fill="x"); self.header_labels[key] = label
        controls = ctk.CTkFrame(header, fg_color="transparent"); controls.grid(row=1, column=0, columnspan=7, sticky="ew", padx=6, pady=(0, 6)); controls.grid_columnconfigure(0, weight=1)
        self.warning_label = ctk.CTkLabel(controls, text="Select a device and target.", text_color=self.theme["error"], anchor="w"); self.warning_label.grid(row=0, column=0, sticky="ew", padx=4)
        self.attach_button = self._button(controls, "Attach", lambda: self._session("attach"), 0, 1)
        self.spawn_button = self._button(controls, "Spawn", lambda: self._session("spawn"), 0, 2)
        self.resume_button = self._button(controls, "Resume", lambda: self._run("Resume", self.runtime.resume, self._show_result), 0, 3)
        self.detach_button = self._button(controls, "Detach", lambda: self._run("Detach", self.runtime.detach, self._show_result), 0, 4)

    def _build_workspace(self):
        self.workspace = ctk.CTkTabview(self, fg_color=self.theme["panel"], border_width=1, border_color=self.theme["border"], segmented_button_fg_color=self.theme["panel_alt"], segmented_button_selected_color=self.theme["red"], segmented_button_selected_hover_color=self.theme["red_hover"], segmented_button_unselected_color=self.theme["panel_alt"], segmented_button_unselected_hover_color=self.theme["gold_dark"], text_color=self.theme["text"])
        self.workspace.grid(row=1, column=0, sticky="nsew", padx=6, pady=(3, 6))
        self.tabs = {name: self.workspace.add(name) for name in ("Library", "Editor", "Runtime", "Messages", "Profiles")}
        for tab in self.tabs.values(): tab.configure(fg_color=self.theme["bg"]); tab.grid_rowconfigure(0, weight=1); tab.grid_columnconfigure(0, weight=1)

    def _panel(self, tab, title):
        frame = ctk.CTkFrame(tab, fg_color=self.theme["panel"], border_width=1, border_color=self.theme["border"], corner_radius=8); frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5); frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=self.theme["gold"], font=self.theme["header_font"], anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4)); return frame

    def _entry(self, parent, placeholder):
        return ctk.CTkEntry(parent, placeholder_text=placeholder, fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"], text_color=self.theme["text"], placeholder_text_color=self.theme["muted"])

    def _combo(self, parent, values, command=None):
        combo = ctk.CTkComboBox(parent, values=values, state="readonly", command=command, fg_color=self.theme["terminal_bg"], border_color=self.theme["gold_dark"], button_color=self.theme["red"], button_hover_color=self.theme["red_hover"], dropdown_fg_color=self.theme["panel_alt"], dropdown_hover_color=self.theme["red"], text_color=self.theme["text"], dropdown_text_color=self.theme["text"]); combo.set(values[0]); return combo

    def _build_library(self):
        frame = self._panel(self.tabs["Library"], "Script Library"); frame.grid_rowconfigure(2, weight=1)
        toolbar = ctk.CTkFrame(frame, fg_color="transparent"); toolbar.grid(row=1, column=0, sticky="ew", padx=7); toolbar.grid_columnconfigure(0, weight=1)
        self.library_search = self._entry(toolbar, "Search scripts, paths, tags..."); self.library_search.grid(row=0, column=0, sticky="ew", padx=3); self.library_search.bind("<KeyRelease>", lambda _e: self._render_library())
        self.kind_filter = self._combo(toolbar, ["All", *[item.value for item in ScriptKind]], lambda _v: self._render_library()); self.kind_filter.grid(row=0, column=1, padx=3)
        self.trust_filter = self._combo(toolbar, ["All", *[item.value for item in TrustState]], lambda _v: self._render_library()); self.trust_filter.grid(row=0, column=2, padx=3)
        self.class_filter = self._combo(toolbar, ["All", "read-only", "state-changing"], lambda _v: self._render_library()); self.class_filter.grid(row=0, column=3, padx=3)
        self.tag_filter = self._entry(toolbar, "Tag"); self.tag_filter.grid(row=0, column=4, padx=3); self.tag_filter.bind("<KeyRelease>", lambda _e: self._render_library())
        split = ctk.CTkFrame(frame, fg_color="transparent"); split.grid(row=2, column=0, sticky="nsew", padx=8, pady=5); split.grid_rowconfigure(0, weight=1); split.grid_columnconfigure(0, weight=3); split.grid_columnconfigure(1, weight=2)
        self.library_list = ctk.CTkScrollableFrame(split, fg_color=self.theme["terminal_bg"], scrollbar_button_color=self.theme["gold_dark"], scrollbar_button_hover_color=self.theme["red_hover"]); self.library_list.grid(row=0, column=0, sticky="nsew", padx=(0, 4)); self.library_list.grid_columnconfigure(0, weight=1)
        self.library_details = ctk.CTkTextbox(split, fg_color=self.theme["terminal_bg"], text_color=self.theme["terminal_text"], border_width=1, border_color=self.theme["border"], wrap="word"); self.library_details.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.grid(row=3, column=0, sticky="ew", padx=7, pady=(2, 7))
        for i in range(4): actions.grid_columnconfigure(i, weight=1)
        for i, (text, callback) in enumerate((("Refresh", self.refresh_library), ("New Script", self.new_script), ("Import", self.import_script), ("Rename", self.rename_script), ("Delete", self.delete_script), ("Trust / Untrust", self.toggle_trust), ("Open Editor", lambda: self.workspace.set("Editor")))): self._button(actions, text, callback, i // 4, i % 4)

    def _build_editor(self):
        frame = self._panel(self.tabs["Editor"], "Agent Editor"); frame.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(frame, fg_color="transparent"); bar.grid(row=1, column=0, sticky="ew", padx=8); bar.grid_columnconfigure(0, weight=1)
        self.editor_name = self._entry(bar, "Select a library item"); self.editor_name.grid(row=0, column=0, sticky="ew", padx=3)
        self.unsaved_label = ctk.CTkLabel(bar, text="Saved", text_color=self.theme["muted"]); self.unsaved_label.grid(row=0, column=1, padx=7)
        self.find_entry = self._entry(bar, "Find text"); self.find_entry.grid(row=0, column=2, padx=3); self._button(bar, "Find", self.find_text, 0, 3)
        self.editor = ctk.CTkTextbox(frame, fg_color=self.theme["terminal_bg"], text_color=self.theme["terminal_text"], font=("Consolas", 13), border_width=1, border_color=self.theme["border"], wrap="none", scrollbar_button_color=self.theme["gold_dark"], scrollbar_button_hover_color=self.theme["red_hover"]); self.editor.grid(row=2, column=0, sticky="nsew", padx=10, pady=5); self.editor.bind("<<Modified>>", self._editor_modified); self.editor.bind("<KeyRelease>", self._cursor_update)
        bottom = ctk.CTkFrame(frame, fg_color="transparent"); bottom.grid(row=3, column=0, sticky="ew", padx=7, pady=(2, 7))
        for i in range(5): bottom.grid_columnconfigure(i, weight=1)
        self.cursor_label = ctk.CTkLabel(bottom, text="Line 1, Column 0", text_color=self.theme["muted"]); self.cursor_label.grid(row=0, column=0, columnspan=5, sticky="w")
        for i, (text, callback) in enumerate((("Save", self.save_editor), ("Save As", self.save_as), ("Revert", self.open_selected), ("Validate", self.validate_selected), ("Load", self.load_selected), ("Reload", self.reload_selected), ("Unload", self.unload_selected), ("Prepare Recipe", self.prepare_recipe), ("Launch Recipe", self.launch_recipe))): self._button(bottom, text, callback, 1 + i // 5, i % 5)

    def _build_runtime(self):
        frame = self._panel(self.tabs["Runtime"], "Active Runtime"); frame.grid_rowconfigure(2, weight=1)
        self.runtime_details = ctk.CTkLabel(frame, text="No active target session.", text_color=self.theme["text"], justify="left", anchor="w", wraplength=900); self.runtime_details.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        split = ctk.CTkFrame(frame, fg_color="transparent"); split.grid(row=2, column=0, sticky="nsew", padx=8, pady=5); split.grid_columnconfigure(0, weight=1); split.grid_columnconfigure(1, weight=1); split.grid_rowconfigure(0, weight=1)
        self.loaded_list = ctk.CTkScrollableFrame(split, fg_color=self.theme["terminal_bg"], scrollbar_button_color=self.theme["gold_dark"], scrollbar_button_hover_color=self.theme["red_hover"]); self.loaded_list.grid(row=0, column=0, sticky="nsew", padx=(0, 4)); self.loaded_list.grid_columnconfigure(0, weight=1)
        rpc = ctk.CTkFrame(split, fg_color=self.theme["panel_alt"]); rpc.grid(row=0, column=1, sticky="nsew", padx=(4, 0)); rpc.grid_columnconfigure(0, weight=1)
        self.post_entry = self._entry(rpc, 'Post JSON message, e.g. {"type":"ping"}'); self.post_entry.grid(row=0, column=0, sticky="ew", padx=8, pady=5); self._button(rpc, "Post Message", self.post_message, 0, 1)
        self.rpc_export = self._entry(rpc, "RPC export name"); self.rpc_export.grid(row=1, column=0, sticky="ew", padx=8, pady=5); self._button(rpc, "List Exports", self.list_exports, 1, 1)
        self.rpc_args = self._entry(rpc, "RPC arguments JSON array"); self.rpc_args.grid(row=2, column=0, sticky="ew", padx=8, pady=5); self._button(rpc, "Call RPC", self.call_rpc, 2, 1)
        self.rpc_result = ctk.CTkTextbox(rpc, height=120, fg_color=self.theme["terminal_bg"], text_color=self.theme["terminal_text"], border_color=self.theme["border"], border_width=1); self.rpc_result.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=8, pady=5); rpc.grid_rowconfigure(3, weight=1)
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.grid(row=3, column=0, sticky="ew", padx=7, pady=5)
        for i in range(4): actions.grid_columnconfigure(i, weight=1)
        for i, (text, callback) in enumerate((("Load Selected", self.load_selected), ("Load Multiple", self.load_multiple), ("Unload Selected", self.unload_selected), ("Unload All", self.unload_all), ("Reload Selected", self.reload_selected), ("Reload All", self.reload_all), ("Resume Spawn", lambda: self._run("Resume", self.runtime.resume, self._show_result)))): self._button(actions, text, callback, i // 4, i % 4)

    def _build_messages(self):
        frame = self._panel(self.tabs["Messages"], "Structured Session Events"); frame.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(frame, fg_color="transparent"); bar.grid(row=1, column=0, sticky="ew", padx=8); bar.grid_columnconfigure(2, weight=1)
        self.event_filter = self._combo(bar, ["All", "session", "script-loaded", "script-unloaded", "send", "error", "binary", "rpc-result", "rpc-error", "warning", "lifecycle"], lambda _v: self.render_events()); self.event_filter.grid(row=0, column=0, padx=3)
        self.script_filter = self._entry(bar, "Filter by script"); self.script_filter.grid(row=0, column=1, sticky="ew", padx=3); self.script_filter.bind("<KeyRelease>", lambda _e: self.render_events())
        self.event_status = ctk.CTkLabel(bar, text="0 events", text_color=self.theme["gold"]); self.event_status.grid(row=0, column=2, sticky="e", padx=5)
        self.message_view = ctk.CTkTextbox(frame, fg_color=self.theme["terminal_bg"], text_color=self.theme["terminal_text"], font=("Consolas", 12), border_width=1, border_color=self.theme["border"], wrap="word"); self.message_view.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.grid(row=3, column=0, sticky="ew", padx=8, pady=5); actions.grid_columnconfigure(0, weight=1)
        self.pause_button = self._button(actions, "Pause Display", self.toggle_pause, 0, 1); self._button(actions, "Clear Display", self.clear_events, 0, 2); self._button(actions, "Copy Selected", self.copy_event, 0, 3); self._button(actions, "Export JSONL", self.export_events, 0, 4); self._button(actions, "Save Binary", self.save_binary, 0, 5)

    def _build_profiles(self):
        frame = self._panel(self.tabs["Profiles"], "Script Chains / Profiles"); frame.grid_rowconfigure(2, weight=1)
        profile_bar = ctk.CTkFrame(frame, fg_color="transparent"); profile_bar.grid(row=1, column=0, sticky="ew", padx=8); profile_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(profile_bar, text="Profile:", text_color=self.theme["muted"]).grid(row=0, column=0, padx=3)
        self.profile_selector = self._combo(profile_bar, ["None"], self._profile_selected); self.profile_selector.grid(row=0, column=1, sticky="ew", padx=3)
        self.profile_notice = ctk.CTkLabel(profile_bar, text="Profiles never run automatically when imported.", text_color=self.theme["text"], anchor="e"); self.profile_notice.grid(row=0, column=2, sticky="e", padx=8)
        self.profile_view = ctk.CTkTextbox(frame, fg_color=self.theme["terminal_bg"], text_color=self.theme["terminal_text"], border_width=1, border_color=self.theme["border"]); self.profile_view.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.grid(row=3, column=0, sticky="ew", padx=8, pady=5)
        for i in range(4): actions.grid_columnconfigure(i, weight=1)
        for i, (text, callback) in enumerate((("Create", self.create_profile), ("Save", self.save_profile), ("Duplicate", self.duplicate_profile), ("Delete", self.delete_profile), ("Add Selected Stage", self.add_profile_stage), ("Move Up", lambda: self.move_stage(-1)), ("Move Down", lambda: self.move_stage(1)), ("Enable / Disable", self.toggle_stage), ("Policy", self.toggle_policy), ("Validate", self.validate_profile), ("Run", self.run_profile), ("Cancel", self.profile_runner.cancel), ("Unload", self.unload_profile))): self._button(actions, text, callback, i // 4, i % 4)

    def set_selected_device(self, device):
        changed = (self.device.serial if self.device else None) != (device.serial if device else None)
        self.device = device
        if changed and self.runtime.session is not None: self._run("Device changed", self.runtime.device_disconnected, self._show_result)
        self._sync_header(); self._update_actions()

    def set_selected_target(self, target):
        changed = target != self.target; self.target = target
        if changed and self.runtime.session is not None: self.warning_label.configure(text="Target changed; detach the stale runtime session.")
        self._sync_header(); self._update_actions()

    def refresh_library(self):
        result = self.library.scan(); self.descriptors = result.descriptors if result.ok else (); self._render_library()
        loaded_profiles = []
        for descriptor in self.descriptors:
            if descriptor.kind is not ScriptKind.PROFILE:
                continue
            source = self.library.load_source(descriptor)
            if source.ok:
                try: loaded_profiles.append(ScriptProfile.from_dict(json.loads(source.text or "{}")))
                except (KeyError, TypeError, json.JSONDecodeError): pass
        if loaded_profiles:
            self.profiles = loaded_profiles; self.selected_profile = loaded_profiles[0]; self._render_profile()
        self._sync_profile_selector()
        if not result.ok: self._error(result.error)

    def _render_library(self):
        for child in self.library_list.winfo_children(): child.destroy()
        items = self.library.search(self.library_search.get(), kind=self.kind_filter.get(), tag=self.tag_filter.get(), trust=self.trust_filter.get(), classification=self.class_filter.get()) if hasattr(self, "library_search") else self.descriptors
        for row, descriptor in enumerate(items):
            button = ctk.CTkButton(self.library_list, text=f"{descriptor.name}\n{descriptor.kind.value} · {descriptor.trust.value} · {descriptor.classification}", command=lambda item=descriptor: self.select_descriptor(item), anchor="w", fg_color=self.theme["red"] if descriptor == self.selected else self.theme["panel_alt"], hover_color=self.theme["red_hover"], text_color=self.theme["text"], border_width=1, border_color=self.theme["gold_dark"] if descriptor == self.selected else self.theme["border"], height=48)
            button.grid(row=row, column=0, sticky="ew", padx=3, pady=3)

    def select_descriptor(self, descriptor):
        self.selected = descriptor; self._render_library(); self.open_selected(); self._render_details(); self._render_loaded(); self._update_actions()

    def _render_details(self):
        item = self.selected; self.library_details.delete("1.0", "end")
        if item: self.library_details.insert("1.0", f"Name: {item.name}\nKind: {item.kind.value}\nTrust: {item.trust.value}\nClassification: {item.classification}\nPath: {item.path}\nSHA-256: {item.sha256}\nTags: {', '.join(item.tags) or 'None'}\nCaution: {item.caution or 'None'}\n\n{item.description}")

    def open_selected(self):
        if not self.selected: return
        result = self.library.load_source(self.selected)
        if not result.ok: self._error(result.error); return
        self.editor.delete("1.0", "end"); self.editor.insert("1.0", result.text or ""); self.editor_name.delete(0, "end"); self.editor_name.insert(0, self.selected.name); self.editor.edit_modified(False); self.editor_dirty = False; self.unsaved_label.configure(text="Saved", text_color=self.theme["muted"])

    def new_script(self):
        name = simpledialog.askstring("New Script", "Script name:", parent=self.winfo_toplevel())
        if name:
            result = self.library.create(name, "// Frida JavaScript agent\n'use strict';\n")
            if result.ok: self.refresh_library(); self.select_descriptor(result.descriptor)
            else: self._error(result.error)

    def import_script(self):
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(), filetypes=[("Script Studio files", "*.js *.ts *.json *.txt *.objection")])
        if path:
            result = self.library.import_file(path)
            if result.ok: self.refresh_library(); self.select_descriptor(result.descriptor); self.warning_label.configure(text="Imported script is untrusted and remains unloaded.")
            else: self._error(result.error)

    def rename_script(self):
        if not self.selected: return
        name = simpledialog.askstring("Rename", "New name:", initialvalue=self.selected.name, parent=self.winfo_toplevel())
        if name:
            result = self.library.rename(self.selected, name)
            if result.ok: self.selected = result.descriptor; self.refresh_library()
            else: self._error(result.error)

    def delete_script(self):
        if self.selected and self.confirm("Delete Script", f"Delete {self.selected.name} from the local library?"):
            result = self.library.delete(self.selected, confirmed=True)
            if result.ok: self.selected = None; self.refresh_library(); self._render_details()
            else: self._error(result.error)

    def toggle_trust(self):
        if not self.selected: return
        trust = TrustState.UNTRUSTED if self.selected.trust is TrustState.TRUSTED_LOCAL else TrustState.TRUSTED_LOCAL
        updated = replace(self.selected, trust=trust); result = self.library.save_metadata(updated)
        if result.ok: self.selected = updated; self.refresh_library(); self._render_details()

    def save_editor(self):
        if not self.selected: return
        result = self.library.save_source(self.selected, self.editor.get("1.0", "end-1c"))
        if result.ok: self.selected = result.descriptor; self.editor_dirty = False; self.unsaved_label.configure(text="Saved", text_color=self.theme["muted"]); self.refresh_library()
        else: self._error(result.error)

    def save_as(self):
        name = self.editor_name.get().strip() or "agent-copy"
        result = self.library.create(name, self.editor.get("1.0", "end-1c"))
        if result.ok: self.refresh_library(); self.select_descriptor(result.descriptor)
        else: self._error(result.error)

    def validate_selected(self):
        if not self.selected: return
        result = self.validator.validate(self.selected, self.editor.get("1.0", "end-1c")); text = "Validation passed." if result.valid else "Errors: " + "; ".join(result.errors)
        if result.warnings: text += "\nWarnings: " + "; ".join(result.warnings)
        self.warning_label.configure(text=text, text_color=self.theme["success"] if result.valid else self.theme["error"]); self.log(f"[SCRIPT VALIDATION] {text}")

    def _confirm_script(self):
        if not self.selected: return None
        untrusted = self.selected.trust is TrustState.UNTRUSTED; changing = self.selected.changes_runtime
        if (untrusted or changing) and not self.confirm("Script Confirmation", f"{self.selected.name} is {self.selected.trust.value} and {self.selected.classification}. Load it into the active target?"): return None
        return {"confirm_untrusted": untrusted, "confirm_state_change": changing}

    def load_selected(self):
        confirmations = self._confirm_script()
        if confirmations is not None: self._run("Load script", lambda: self.runtime.load_script(self.selected, **confirmations), self._show_result)

    def unload_selected(self):
        if self.selected: self._run("Unload script", lambda: self.runtime.unload_script(self.selected.script_id), self._show_result)

    def reload_selected(self):
        confirmations = self._confirm_script()
        if confirmations is not None and self.selected: self._run("Reload script", lambda: self.runtime.reload_script(self.selected.script_id, **confirmations), self._show_result)

    def unload_all(self): self._run("Unload all", self.runtime.unload_all, lambda _r: self._render_loaded())
    def reload_all(self): self._run("Reload all", lambda: self.runtime.reload_all(confirm_untrusted=True, confirm_state_change=True), lambda _r: self._render_loaded())

    def load_multiple(self):
        candidates = tuple(item for item in self.descriptors if item.enabled and item.kind is ScriptKind.FRIDA and not item.path.casefold().endswith(".ts"))
        if not candidates: self._error("No enabled Frida JavaScript library items are available."); return
        risky = any(item.trust is TrustState.UNTRUSTED or item.changes_runtime for item in candidates)
        if risky and not self.confirm("Load Multiple Scripts", f"Load {len(candidates)} enabled scripts, including explicitly marked untrusted or state-changing items?"): return
        self._run("Load multiple", lambda: self.runtime.load_multiple(candidates, confirm_untrusted=risky, confirm_state_change=risky), self._show_result)

    def prepare_recipe(self):
        if not self.selected or self.selected.kind is not ScriptKind.OBJECTION_RECIPE:
            self._error("Select an Objection recipe first."); return
        if not self.objection_recipes: self._error("Objection recipe support is unavailable."); return
        if not self.target: self._error("Select an application target first."); return
        commands = self.objection_recipes.parse(self.editor.get("1.0", "end-1c"))
        if not self.confirm("Prepare Objection Recipe", "Commands to launch:\n\n" + "\n".join(commands)): return
        self._run("Prepare recipe", lambda: self.objection_recipes.prepare(self.target.identifier or self.target.name, "socket", self.device.serial if self.device else None, self.selected.path, self.editor.get("1.0", "end-1c"), confirmed=True), self._show_recipe)

    def _show_recipe(self, result):
        self.prepared_recipe = result if result.ok else None
        text = "\n".join(result.commands)
        if result.launch_command: text += "\n\nLaunch argv: " + " ".join(result.launch_command)
        if result.guidance: text += "\n\n" + result.guidance
        if result.error: text += "\n\n" + result.error
        self.rpc_result.delete("1.0", "end"); self.rpc_result.insert("1.0", text)
        self.warning_label.configure(text="Recipe prepared; review the visible command order before launch." if result.ok else result.guidance or result.error, text_color=self.theme["gold"] if result.ok else self.theme["error"])

    def launch_recipe(self):
        if not self.prepared_recipe: self._error("Prepare and review a supported recipe first."); return
        if not self.confirm("Launch Objection Recipe", "Launch the reviewed recipe in an external terminal?"): return
        self._run("Launch recipe", lambda: self.objection_recipes.launch(self.prepared_recipe), lambda result: self.warning_label.configure(text=result.output, text_color=self.theme["success"] if result.ok else self.theme["error"]))

    def _session(self, mode):
        operation = (lambda: self.runtime.spawn(self.device.serial if self.device else None, self.target)) if mode == "spawn" else (lambda: self.runtime.attach(self.device.serial if self.device else None, self.target))
        self._run(mode.title(), operation, self._show_result)

    def _show_result(self, result):
        results = result if isinstance(result, tuple) else (result,); errors = [item.error for item in results if isinstance(item, RuntimeResult) and not item.ok]
        if errors: self._error("; ".join(error for error in errors if error))
        warnings = [item.warning for item in results if isinstance(item, RuntimeResult) and item.warning]
        if warnings: self.warning_label.configure(text="; ".join(warnings), text_color=self.theme["error"])
        self._sync_header(); self._render_loaded(); self._update_actions()

    def _render_loaded(self):
        for child in self.loaded_list.winfo_children(): child.destroy()
        for row, record in enumerate(self.runtime.list_loaded()): ctk.CTkLabel(self.loaded_list, text=f"{record.descriptor.name}\n{record.state} · {len(record.rpc_exports)} RPC exports", text_color=self.theme["gold"] if record.descriptor == self.selected else self.theme["text"], anchor="w", justify="left").grid(row=row, column=0, sticky="ew", padx=7, pady=5)
        self.runtime_details.configure(text=f"Target: {self.target.display_label if self.target else 'None'}\nState: {self.runtime.state.value}\nLoaded scripts: {len(self.runtime.loaded)}")

    def post_message(self):
        if not self.selected: return
        try: message = json.loads(self.post_entry.get())
        except json.JSONDecodeError as exc: self._error(f"Invalid message JSON: {exc}"); return
        self._run("Post message", lambda: self.runtime.post(self.selected.script_id, message), self._show_result)

    def list_exports(self):
        if self.selected: self._run("List RPC", lambda: self.runtime.list_rpc_exports(self.selected.script_id), lambda result: self._rpc_output(result.value if result.ok else result.error))

    def call_rpc(self):
        if not self.selected: return
        try: args = json.loads(self.rpc_args.get() or "[]"); assert isinstance(args, list)
        except (json.JSONDecodeError, AssertionError): self._error("RPC arguments must be a JSON array."); return
        self._run("Call RPC", lambda: self.runtime.call_rpc(self.selected.script_id, self.rpc_export.get().strip(), args), lambda result: self._rpc_output(result.value if result.ok else result.error))

    def _rpc_output(self, value): self.rpc_result.delete("1.0", "end"); self.rpc_result.insert("1.0", json.dumps(value, indent=2, default=str)); self._sync_header()

    def queue_event(self, event): self.after(0, self._accept_event, event)
    def _accept_event(self, event): self.events.append(event); self.event_status.configure(text=f"{len(self.events)} events"); self.log(f"[SCRIPT EVENT] {event.display_text}"); self.render_events()
    def render_events(self):
        if self.display_paused: return
        kind = self.event_filter.get(); script = self.script_filter.get().strip().casefold(); shown = [event for event in self.events if (kind == "All" or event.event_type.value == kind) and (not script or script in (event.script_name or "").casefold())]
        self.message_view.delete("1.0", "end"); self.message_view.insert("1.0", "\n\n".join(event.display_text + (f"\n{event.stack_trace}" if event.stack_trace else "") for event in shown)); self.event_status.configure(text=f"{len(shown)} shown / {len(self.events)} collected")
    def toggle_pause(self): self.display_paused = not self.display_paused; self.pause_button.configure(text="Resume Display" if self.display_paused else "Pause Display"); self.render_events()
    def clear_events(self): self.events.clear(); self.render_events()
    def copy_event(self):
        try: text = self.message_view.get("sel.first", "sel.last")
        except Exception: text = self.message_view.get("1.0", "end-1c")
        self.clipboard_clear(); self.clipboard_append(text)
    def export_events(self):
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), defaultextension=".jsonl")
        if path: Path(path).write_text("\n".join(json.dumps(event.to_dict(), default=str) for event in self.events), encoding="utf-8")
    def save_binary(self):
        event = next((item for item in reversed(self.events) if item.binary is not None), None)
        if not event: self._error("No binary event is available."); return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), defaultextension=".bin")
        if path: Path(path).write_bytes(event.binary)

    def create_profile(self):
        if not self.selected: self._error("Select a script for the first profile stage."); return
        name = simpledialog.askstring("Profile", "Profile name:", parent=self.winfo_toplevel())
        if name: self.selected_profile = ScriptProfile(name, stages=(ScriptStage(self.selected.script_id),)); self.profiles.append(self.selected_profile); self._sync_profile_selector(); self._render_profile()
    def save_profile(self):
        if not self.selected_profile: return
        text = json.dumps(self.selected_profile.to_dict(), indent=2)
        existing = next((item for item in self.descriptors if item.kind is ScriptKind.PROFILE and item.name == self.selected_profile.name), None)
        result = self.library.save_source(existing, text) if existing else self.library.create(self.selected_profile.name, text, suffix=".json", kind=ScriptKind.PROFILE)
        if result.ok: self.refresh_library(); self.profile_notice.configure(text="Profile saved; it will never run automatically.", text_color=self.theme["success"])
        else: self._error(result.error)
    def duplicate_profile(self):
        if self.selected_profile: self.selected_profile = ScriptProfile(self.selected_profile.name + " Copy", self.selected_profile.description, self.selected_profile.target_requirement, self.selected_profile.stages); self.profiles.append(self.selected_profile); self._sync_profile_selector(); self._render_profile()
    def delete_profile(self):
        if self.selected_profile and self.confirm("Delete Profile", f"Delete {self.selected_profile.name}?"): self.profiles.remove(self.selected_profile); self.selected_profile = self.profiles[0] if self.profiles else None; self._sync_profile_selector(); self._render_profile()
    def add_profile_stage(self):
        if not self.selected_profile or not self.selected: return
        stages = (*self.selected_profile.stages, ScriptStage(self.selected.script_id))
        self.selected_profile = replace(self.selected_profile, stages=stages, digest=""); self._replace_current_profile(); self._render_profile()
    def move_stage(self, direction):
        if not self.selected_profile or len(self.selected_profile.stages) < 2: return
        stages = list(self.selected_profile.stages); item = stages.pop(0); stages.insert(max(0, min(len(stages), direction)), item); self.selected_profile = replace(self.selected_profile, stages=tuple(stages), digest=""); self._replace_current_profile(); self._render_profile()
    def toggle_stage(self):
        if self.selected_profile and self.selected_profile.stages:
            stages = list(self.selected_profile.stages); stages[0] = replace(stages[0], enabled=not stages[0].enabled); self.selected_profile = replace(self.selected_profile, stages=tuple(stages), digest=""); self._replace_current_profile(); self._render_profile()
    def toggle_policy(self):
        if self.selected_profile and self.selected_profile.stages:
            stages = list(self.selected_profile.stages); stages[0] = replace(stages[0], failure_policy=FailurePolicy.CONTINUE if stages[0].failure_policy is FailurePolicy.STOP else FailurePolicy.STOP); self.selected_profile = replace(self.selected_profile, stages=tuple(stages), digest=""); self._replace_current_profile(); self._render_profile()
    def validate_profile(self):
        if self.selected_profile: self._profile_result(self.profile_runner.validate(self.selected_profile, {item.script_id: item for item in self.descriptors}))
    def run_profile(self):
        if not self.selected_profile: return
        if not self.confirm("Run Profile", "Load the visible enabled profile stages in order?"): return
        self._run("Run profile", lambda: self.profile_runner.run(self.selected_profile, {item.script_id: item for item in self.descriptors}, confirm_untrusted=True, confirm_state_change=True), self._profile_result)
    def unload_profile(self): self._run("Unload profile", self.profile_runner.unload, lambda _r: self._render_loaded())
    def _profile_result(self, result): self.profile_notice.configure(text="Profile valid." if result.ok else "; ".join(result.errors), text_color=self.theme["success"] if result.ok else self.theme["error"]); self._render_profile(); self._render_loaded()
    def _render_profile(self): self.profile_view.delete("1.0", "end"); self.profile_view.insert("1.0", json.dumps(self.selected_profile.to_dict(), indent=2) if self.selected_profile else "No profile selected.")
    def _sync_profile_selector(self):
        if not hasattr(self, "profile_selector"): return
        values = [profile.name for profile in self.profiles] or ["None"]
        self.profile_selector.configure(values=values); self.profile_selector.set(self.selected_profile.name if self.selected_profile else values[0])
    def _profile_selected(self, name):
        self.selected_profile = next((profile for profile in self.profiles if profile.name == name), None); self._render_profile()
    def _replace_current_profile(self):
        if not self.selected_profile: return
        for index, profile in enumerate(self.profiles):
            if profile.name == self.selected_profile.name: self.profiles[index] = self.selected_profile; break

    def find_text(self):
        index = self.editor.search(self.find_entry.get(), self.editor.index("insert"), stopindex="end", nocase=True)
        if index: self.editor.mark_set("insert", index); self.editor.see(index)
    def _editor_modified(self, _e):
        if self.editor.edit_modified(): self.editor_dirty = True; self.unsaved_label.configure(text="Unsaved", text_color=self.theme["error"]); self.editor.edit_modified(False)
    def _cursor_update(self, _e=None): line, column = self.editor.index("insert").split("."); self.cursor_label.configure(text=f"Line {line}, Column {column}")
    def _sync_header(self):
        available = self.runtime.adapter.availability(); info = available.value or {}
        diagnosis = self.runtime.last_diagnosis
        self.header_labels["device"].configure(text=self.device.display_name if self.device else "None"); self.header_labels["target"].configure(text=(self.target.identifier or self.target.name) if self.target else "None"); self.header_labels["runtime"].configure(text=self.runtime.state.value); self.header_labels["python"].configure(text=info.get("version", "Missing") if available.ok else "Missing"); self.header_labels["server"].configure(text=diagnosis.server_version if diagnosis and diagnosis.server_version else "Unknown"); self.header_labels["versions"].configure(text="Mismatch" if self.runtime.version_warning else "Match" if diagnosis and diagnosis.versions_match else "Unknown"); self.header_labels["loaded"].configure(text=str(len(self.runtime.loaded)))
        self.warning_label.configure(text=(available.error if not available.ok else "Ready for an explicitly selected device and target."), text_color=self.theme["error"] if not available.ok else self.theme["gold"])
    def _update_actions(self):
        ready = bool(self.device and self.device.connected and self.target); self.attach_button.configure(state="normal" if ready else "disabled"); self.spawn_button.configure(state="normal" if ready and self.target.application_identifier else "disabled"); active = self.runtime.session is not None; self.detach_button.configure(state="normal" if active else "disabled"); self.resume_button.configure(state="normal" if self.runtime.spawned_pid else "disabled")
    def _run(self, title, operation, callback):
        self.log(f"[SCRIPT STUDIO] {title}...")
        def guarded():
            try: return True, operation()
            except Exception as exc: return False, exc
        BackgroundWorker(guarded, callback=lambda result: self.after(0, self._finish, title, result, callback)).start()
    def _finish(self, title, result, callback):
        ok, value = result
        if not ok: self._error(f"{title}: {value}"); return
        callback(value); self.log(f"[SCRIPT STUDIO] {title} complete.")
    def _error(self, text): self.warning_label.configure(text=text or "Operation failed.", text_color=self.theme["error"]); self.log(f"[SCRIPT STUDIO ERROR] {text}")
