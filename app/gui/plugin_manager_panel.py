"""Responsive Gothic local Plugin Manager; no automatic plugin execution."""
from __future__ import annotations
import json
from pathlib import Path
from tkinter import filedialog,messagebox,simpledialog
import customtkinter as ctk
from app.core.worker import BackgroundWorker
from app.plugins.plugin_capabilities import HIGH_IMPACT
from app.plugins.plugin_ui import PluginPanelSpec
class PluginSpecFrame(ctk.CTkFrame):
    def __init__(self,parent,theme,spec):
        super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.spec=None;self.pages={};self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(2,weight=1)
        self.title_label=ctk.CTkLabel(self,text="",text_color=theme["gold"],font=theme["header_font"],anchor="w",wraplength=760);self.title_label.grid(row=0,column=0,sticky="ew",padx=8,pady=4)
        self.status_label=ctk.CTkLabel(self,text="",text_color=theme["muted"],anchor="w",wraplength=900);self.status_label.grid(row=1,column=0,sticky="ew",padx=8)
        self.tabs=ctk.CTkTabview(self,fg_color=theme["panel"],segmented_button_fg_color=theme["panel_alt"],segmented_button_selected_color=theme["red"],segmented_button_selected_hover_color=theme["red_hover"],segmented_button_unselected_color=theme["panel_alt"],segmented_button_unselected_hover_color=theme["gold_dark"],text_color=theme["text"]);self.tabs.grid(row=2,column=0,sticky="nsew",padx=5,pady=5)
        self.update_spec(spec)
    def update_spec(self,spec):
        if spec==self.spec:return
        selected=self.tabs.get() if self.pages else ""
        self.spec=spec;self.title_label.configure(text=spec.title);self.status_label.configure(text=" · ".join(f"{k}: {v}" for k,v in spec.status.items()))
        existing=set(self.pages);wanted={view.name for view in spec.views}
        for name in existing-wanted:self.tabs.delete(name);self.pages.pop(name,None)
        for view in spec.views:
            body=self.pages.get(view.name)
            if body is None:
                page=self.tabs.add(view.name);page.grid_columnconfigure(0,weight=1);page.grid_rowconfigure(0,weight=1);body=ctk.CTkTextbox(page,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_color=self.theme["border"],border_width=1,wrap="word");body.grid(row=0,column=0,sticky="nsew",padx=4,pady=4);self.pages[view.name]=body
            text=view.body+("\n\n"+"\n".join(f"{k}: {v}" for k,v in view.rows) if view.rows else "")+(f"\n\nWARNING: {view.warning}" if view.warning else "");body.configure(state="normal");body.delete("1.0","end");body.insert("1.0",text);body.configure(state="disabled")
        if selected in self.pages:self.tabs.set(selected)
class PluginManagerPanel(ctk.CTkFrame):
    SECTIONS=("Official Catalog","Installed","Active Panels","Details","Permissions","Contributions","Diagnostics","SDK")
    def __init__(self,parent,theme,manager,log,confirm=None):
        super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.manager=manager;self.log=log;self.confirm=confirm or (lambda t,m:messagebox.askyesno(t,m,parent=self.winfo_toplevel()));self.selected=None;self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1);self._header();self.tabs=ctk.CTkTabview(self,fg_color=theme["panel"],segmented_button_fg_color=theme["panel_alt"],segmented_button_selected_color=theme["red"],segmented_button_selected_hover_color=theme["red_hover"],segmented_button_unselected_color=theme["panel_alt"],segmented_button_unselected_hover_color=theme["gold_dark"],text_color=theme["text"]);self.tabs.grid(row=1,column=0,sticky="nsew",padx=6,pady=4);self.views={n:self.tabs.add(n) for n in self.SECTIONS}
        for v in self.views.values():v.configure(fg_color=theme["bg"]);v.grid_columnconfigure(0,weight=1);v.grid_rowconfigure(1,weight=1)
        self._build();self.unsubscribe=self.manager.registry.subscribe(lambda _items:self.after(0,self.refresh));self.refresh()
    def _button(self,p,text,cmd,row,col):b=ctk.CTkButton(p,text=text,command=cmd,fg_color=self.theme["red"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold_dark"],height=30);b.grid(row=row,column=col,sticky="ew",padx=3,pady=3);return b
    def _text(self,p):t=ctk.CTkTextbox(p,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_width=1,border_color=self.theme["border"],wrap="word");t.grid(row=1,column=0,sticky="nsew",padx=6,pady=4);t.configure(state="disabled");return t
    def _set(self,w,text):w.configure(state="normal");w.delete("1.0","end");w.insert("1.0",text);w.configure(state="disabled")
    def _header(self):
        h=ctk.CTkFrame(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["gold_dark"]);h.grid(row=0,column=0,sticky="ew",padx=6,pady=4);h.grid_columnconfigure(0,weight=1);self.summary=ctk.CTkLabel(h,text="Plugins",text_color=self.theme["gold"],anchor="w",wraplength=760);self.summary.grid(row=0,column=0,sticky="ew",padx=7);self._button(h,"Refresh",self.refresh,0,1);self._button(h,"Install Local Plugin",self.install,0,2);self._button(h,"Verify All",self.verify_all,0,3);self._button(h,"Disable All Third-Party",self.disable_all,0,4);self.warning=ctk.CTkLabel(h,text="Third-party plugins remain disabled and untrusted by default.",text_color=self.theme["gold"],anchor="w",wraplength=900);self.warning.grid(row=1,column=0,columnspan=5,sticky="ew",padx=7)
    def _build(self):
        p=self.views["Official Catalog"];self.official_cards=ctk.CTkScrollableFrame(p,fg_color=self.theme["bg"]);self.official_cards.grid(row=0,column=0,rowspan=2,sticky="nsew");self.official_cards.grid_columnconfigure(0,weight=1)
        p=self.views["Installed"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self.search=ctk.CTkEntry(bar,placeholder_text="Search plugins",fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.search.grid(row=0,column=0,sticky="ew",padx=3);self._button(bar,"Apply",self.render,0,1)
        for i,(n,c) in enumerate((("Enable",self.enable),("Disable",self.disable),("Load",self.load),("Unload",self.unload),("Reload",self.reload),("Uninstall",self.uninstall)),2):self._button(bar,n,c,0,i)
        self.installed=self._text(p)
        for name in ("Details","Permissions","Contributions","Diagnostics","SDK"):self.__dict__[name.lower()+"_view"]=self._text(self.views[name])
        self.active_host=ctk.CTkFrame(self.views["Active Panels"],fg_color=self.theme["bg"]);self.active_host.grid(row=0,column=0,rowspan=2,sticky="nsew");self.active_host.grid_columnconfigure(0,weight=1);self.active_host.grid_rowconfigure(0,weight=1)
        p=self.views["Permissions"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Approve Selected Requested",self.approve,0,0);self._button(bar,"Revoke Trust",self.revoke,0,1)
        p=self.views["Diagnostics"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Copy Diagnostics",lambda:self._copy(self.diagnostics_view.get("1.0","end-1c")),0,0);self._button(bar,"Quarantine",self.quarantine,0,1)
        p=self.views["SDK"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Create Plugin Skeleton",self.skeleton,0,0)
    def refresh(self):self.manager.refresh();self.render();self.render_official();self.render_active()
    def render(self):
        items=self.manager.list(self.search.get() if hasattr(self,"search") else "");self.selected=self.selected if self.selected and any(v.plugin_id==self.selected.plugin_id for v in items) else (items[-1] if items else None);statuses=self.manager.loader.statuses;active=sum(s.state.value=="active" for s in statuses.values());failed=sum(s.state.value=="failed" for s in statuses.values());enabled=sum(v.enabled for v in items);untrusted=sum(v.trust_state.value=="untrusted" for v in items);changed=self.manager.changed_digest_count();self.summary.configure(text=f"Installed {len(items)} · Enabled {enabled} · Active {active} · Untrusted {untrusted} · Failed {failed} · Changed {changed}");self._set(self.installed,"\n\n".join(f"{m.display_label}\nID: {m.plugin_id}\nDigest: {m.package_digest}\nStatus: {getattr(statuses.get(m.plugin_id),'state','discovered')}" for m in items) or "No installed plugins. Files in examples do not install or execute automatically.");self._details()
    def _details(self):
        m=self.selected
        if not m:
            for name in ("details_view","permissions_view","contributions_view","diagnostics_view"):self._set(getattr(self,name),"No plugin selected.")
        else:
            self._set(self.details_view,json.dumps(m.to_dict(),indent=2,default=str));approved=self.manager.trust.approved(m.plugin_id,m.package_digest);self._set(self.permissions_view,"Requested:\n"+"\n".join(f"- {v}{' — HIGH IMPACT' if v in HIGH_IMPACT else ''}" for v in m.requested_capabilities)+"\n\nApproved:\n"+"\n".join(approved));self._set(self.contributions_view,"\n".join(f"{c.contribution_type} · {c.contribution_id} · {c.title}" for c in self.manager.registry.by_plugin(m.plugin_id)) or "No active contributions; contributions register only after explicit trusted load.");status=self.manager.loader.statuses.get(m.plugin_id);self._set(self.diagnostics_view,f"Digest: {m.package_digest}\nTrust: {m.trust_state.value}\nEnabled: {m.enabled}\nLoader: {getattr(status,'state','discovered')}\nLast error: {getattr(status,'last_error','')}")
        self._set(self.sdk_view,"Plugin API v1.0\n\nDocumentation: docs/plugin-sdk/README.md\nHarmless disabled example: plugins/examples/hello_plugin\n\nPython plugins are trusted code. In-process loading is not a hardened sandbox. No download, update, enable, trust, or load occurs automatically.")
    def render_official(self):
        for child in self.official_cards.winfo_children():child.destroy()
        for row,item in enumerate(self.manager.official()):
            card=ctk.CTkFrame(self.official_cards,fg_color=self.theme["panel_alt"],border_width=1,border_color=self.theme["border"]);card.grid(row=row,column=0,sticky="ew",padx=8,pady=6);card.grid_columnconfigure(0,weight=1);m=item.manifest
            ctk.CTkLabel(card,text=f"{m.name} · {m.version} · Official",text_color=self.theme["gold"],anchor="w",font=self.theme["header_font"],wraplength=700).grid(row=0,column=0,sticky="ew",padx=10,pady=(8,2));ctk.CTkLabel(card,text=f"{m.description}\nCapabilities: {len(m.requested_capabilities)} · {'Installed' if item.installed else 'Available'}",text_color=self.theme["text"],anchor="w",justify="left",wraplength=760).grid(row=1,column=0,sticky="ew",padx=10,pady=(0,8));button=self._button(card,"Installed" if item.installed else "Install",lambda pid=m.plugin_id,digest=item.package_digest:self.install_official(pid,digest),0,1);button.configure(state="disabled" if item.installed else "normal")
    def install_official(self,plugin_id=None,digest=""):
        if plugin_id:self._run("Install official plugin",lambda:self.manager.install_official(plugin_id,digest))
    def render_active(self):
        for child in self.active_host.winfo_children():child.destroy()
        panels=list(self.manager.registry.list("pentest-panel"))
        if not panels:ctk.CTkLabel(self.active_host,text="No active plugin panels. Install, approve, enable, and explicitly load a plugin.",text_color=self.theme["muted"],wraplength=800).grid(row=0,column=0,sticky="nsew");return
        for row,contribution in enumerate(panels):
            line=ctk.CTkFrame(self.active_host,fg_color=self.theme["panel_alt"],border_width=1,border_color=self.theme["border"]);line.grid(row=row,column=0,sticky="ew",padx=8,pady=5);line.grid_columnconfigure(0,weight=1);host=self.winfo_toplevel();opened=bool(getattr(host,"addon_window_host",None) and host.addon_window_host.is_open(contribution.contribution_id));ctk.CTkLabel(line,text=f"{contribution.title}\nLoaded · Window {'open' if opened else 'closed'}",text_color=self.theme["gold"],anchor="w",justify="left").grid(row=0,column=0,sticky="ew",padx=8,pady=6);self._button(line,"Focus" if opened else "Open",lambda cid=contribution.contribution_id:getattr(self.winfo_toplevel(),"open_addon_window")(cid),0,1);self._button(line,"Unload",lambda pid=contribution.plugin_id:self._done("Unload",self.manager.unload(pid)),0,2)
    def open_contribution(self,contribution_id):
        item=next((value for value in self.manager.registry.list("pentest-panel") if value.contribution_id==contribution_id),None)
        self.tabs.set("Active Panels")
        if item and hasattr(self.winfo_toplevel(),"open_addon_window"):self.winfo_toplevel().open_addon_window(item.contribution_id)
    def _run(self,title,fn):self.warning.configure(text=title+"…",text_color=self.theme["gold"]);BackgroundWorker(fn,callback=lambda r:self.after(0,self._done,title,r)).start()
    def _done(self,title,r):self.warning.configure(text=(title+" complete.") if r.ok else (r.error or title+" failed."),text_color=self.theme["success"] if r.ok else self.theme["error"]);self.refresh()
    def install(self):
        path=filedialog.askopenfilename(parent=self.winfo_toplevel(),title="Select local plugin ZIP") or filedialog.askdirectory(parent=self.winfo_toplevel(),title="Select local plugin directory")
        if path:self._run("Store disabled plugin",lambda:self.manager.install(path))
    def _id(self):return self.selected.plugin_id if self.selected else None
    def enable(self):
        if self._id():self._done("Enable",self.manager.enable(self._id()))
    def disable(self):
        if self._id():self._done("Disable",self.manager.disable(self._id()))
    def load(self):
        if self._id() and self.confirm("Load Trusted Plugin","Load this explicitly enabled, digest-verified plugin as trusted Python code?"):self._done("Load",self.manager.load(self._id()))
    def unload(self):
        if self._id():self._done("Unload",self.manager.unload(self._id()))
    def reload(self):
        if self._id() and self.confirm("Reload Plugin","Unload and reload this trusted plugin?"):self._done("Reload",self.manager.reload(self._id()))
    def uninstall(self):
        if self._id() and self.confirm("Uninstall Plugin","Remove executable plugin files? Plugin state and assessment data remain preserved."):self._done("Uninstall",self.manager.uninstall(self._id(),True))
    def approve(self):
        if not self.selected:return
        high=bool(set(self.selected.requested_capabilities)&HIGH_IMPACT);confirmed=not high or self.confirm("High-impact Plugin Permissions","Approve the displayed high-impact capabilities for this exact package digest?");self._done("Trust approval",self.manager.approve(self._id(),self.selected.requested_capabilities,confirmed))
    def revoke(self):
        if self._id():self._done("Revoke trust",self.manager.revoke(self._id()))
    def verify_all(self):
        for m in tuple(self.manager.list()):self.manager.verify(m.plugin_id)
        self.refresh()
    def disable_all(self):
        for m in tuple(self.manager.list()):
            if m.trust_state.value!="built-in":self.manager.disable(m.plugin_id)
        self.refresh()
    def quarantine(self):
        if self._id() and self.confirm("Quarantine Plugin","Disable, revoke trust, and move this plugin package to quarantine?"):self._done("Quarantine",self.manager.quarantine(self._id()))
    def skeleton(self):
        pid=simpledialog.askstring("Plugin Skeleton","Stable plugin ID (lowercase):",parent=self.winfo_toplevel())
        if not pid:return
        dest=self.manager.store.root/"disabled"/pid/"0.1.0"
        if dest.exists():self.warning.configure(text="Skeleton path already exists.",text_color=self.theme["error"]);return
        try:
            dest.mkdir(parents=True);(dest/"manifest.json").write_text(json.dumps({"plugin_id":pid,"name":pid,"version":"0.1.0","entry_point":"plugin.py:Plugin","enabled":False},indent=2),encoding="utf-8");(dest/"plugin.py").write_text("class Plugin:\n    def activate(self, api):\n        return ()\n    def deactivate(self):\n        pass\n",encoding="utf-8");self.warning.configure(text=f"Disabled skeleton created at {dest}. It was not imported, enabled, or executed.",text_color=self.theme["gold"])
        except (OSError,ValueError) as exc:self.warning.configure(text=str(exc),text_color=self.theme["error"])
    def _copy(self,text):self.clipboard_clear();self.clipboard_append(text)
    def set_selected_device(self,_):pass
    def set_selected_target(self,_):pass
    def cleanup(self):
        if getattr(self,"unsubscribe",None):self.unsubscribe();self.unsubscribe=None
        self.manager.shutdown()
