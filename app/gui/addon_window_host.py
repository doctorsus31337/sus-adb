"""Core-owned detachable addon windows built only from immutable SDK specs."""
from __future__ import annotations
import customtkinter as ctk
from app.gui.plugin_manager_panel import PluginSpecFrame
from app.plugins.plugin_ui import AddonWindowSpec,PluginPanelSpec,resolve_ui_mode,clamp_addon_geometry

class AddonWindowHost:
    def __init__(self,parent,theme,manager,geometry_store=None):
        self.parent=parent;self.theme=theme;self.manager=manager;self.geometry_store=geometry_store if geometry_store is not None else {};self.windows={};self.owners={};self.errors={};self.unsubscribe=manager.subscribe(self._manager_event)
    def _manager_event(self,event,plugin_id):
        if event in {"unload","uninstall"}:self.close_plugin(plugin_id)
    def spec_for(self,contribution):
        try:
            panel=contribution.factory(self.manager.plugin_context(contribution.plugin_id)) if contribution.factory else None
            if not isinstance(panel,PluginPanelSpec):raise TypeError("Addon factory did not return PluginPanelSpec.")
            meta=contribution.metadata;return AddonWindowSpec(contribution.contribution_id,contribution.title,panel,resolve_ui_mode(meta.get("ui_mode")),int(meta.get("default_width",1080)),int(meta.get("default_height",720)),int(meta.get("minimum_width",820)),int(meta.get("minimum_height",560)),bool(meta.get("singleton",True)),bool(meta.get("embedded_summary",False)),str(meta.get("icon","⚙")))
        except Exception as exc:self.errors[contribution.contribution_id]=str(exc)[:240];return None
    def open(self,contribution_id):
        existing=self.windows.get(contribution_id)
        if existing is not None and existing.winfo_exists():existing.deiconify();existing.lift();existing.focus_force();return existing
        contribution=next((c for c in self.manager.registry.list("pentest-panel") if c.contribution_id==contribution_id),None)
        if contribution is None:self.errors[contribution_id]="Loaded addon contribution was not found.";return None
        spec=self.spec_for(contribution)
        if spec is None:return None
        try:
            window=ctk.CTkToplevel(self.parent);window.title(f"SUS-ADB — {spec.title}");window.configure(fg_color=self.theme["bg"]);window.minsize(spec.minimum_width,spec.minimum_height)
            window.geometry(clamp_addon_geometry(self.geometry_store.get(contribution_id),window.winfo_screenwidth(),window.winfo_screenheight(),spec));window.grid_rowconfigure(0,weight=1);window.grid_columnconfigure(0,weight=1)
            PluginSpecFrame(window,self.theme,spec.panel).grid(row=0,column=0,sticky="nsew",padx=12,pady=12)
            self.windows[contribution_id]=window;self.owners[contribution_id]=contribution.plugin_id
            window.protocol("WM_DELETE_WINDOW",lambda:self.close(contribution_id));return window
        except Exception as exc:self.errors[contribution_id]=str(exc)[:240];return None
    def close(self,contribution_id):
        window=self.windows.pop(contribution_id,None);self.owners.pop(contribution_id,None)
        if window is not None and window.winfo_exists():self.geometry_store[contribution_id]=window.geometry();window.destroy()
    def close_plugin(self,plugin_id):
        for cid,owner in tuple(self.owners.items()):
            if owner==plugin_id:self.close(cid)
    def is_open(self,contribution_id):
        window=self.windows.get(contribution_id);return bool(window is not None and window.winfo_exists())
    def shutdown(self):
        for cid in tuple(self.windows):self.close(cid)
        if self.unsubscribe:self.unsubscribe();self.unsubscribe=None
