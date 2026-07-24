"""Focused non-modal Add-ons Center with explicit lifecycle cards."""
from __future__ import annotations
from tkinter import filedialog,messagebox
import customtkinter as ctk
from app.core.app_metadata import METADATA
from app.gui.customtkinter_compat import PendingCallbackOwner,focused_within,safe_focus,widget_exists
from app.plugins.plugin_capabilities import HIGH_IMPACT
from app.plugins.addon_presenter import card_actions,card_spec

class AddonCard(ctk.CTkFrame):
    def __init__(self,parent,theme,spec,actions):
        super().__init__(parent,fg_color=theme["panel_alt"],border_width=1,border_color=theme["border"],corner_radius=10);self.plugin_id=spec.plugin_id;self.theme=theme;self.action_callback=actions;self.spec=None;self.buttons={};self.grid_columnconfigure(0,weight=1)
        self.name_label=ctk.CTkLabel(self,text="",text_color=theme["gold"],font=theme["header_font"],anchor="w",wraplength=390);self.name_label.grid(row=0,column=0,sticky="ew",padx=12,pady=(10,2))
        self.version_label=ctk.CTkLabel(self,text="",text_color=theme["muted"],anchor="w");self.version_label.grid(row=1,column=0,sticky="ew",padx=12)
        self.description_label=ctk.CTkLabel(self,text="",text_color=theme["text"],anchor="nw",justify="left",wraplength=390,height=54);self.description_label.grid(row=2,column=0,sticky="ew",padx=12,pady=5)
        self.state_label=ctk.CTkLabel(self,text="",text_color=theme["gold"],anchor="w",justify="left");self.state_label.grid(row=3,column=0,sticky="ew",padx=12)
        self.privacy_label=ctk.CTkLabel(self,text="",text_color=theme["muted"],anchor="nw",justify="left",wraplength=390,height=48);self.privacy_label.grid(row=4,column=0,sticky="ew",padx=12,pady=5)
        self.bar=ctk.CTkFrame(self,fg_color="transparent");self.bar.grid(row=5,column=0,sticky="ew",padx=8,pady=(2,10));self.update_spec(spec)
    def update_spec(self,spec):
        if spec.plugin_id!=self.plugin_id:raise ValueError("Addon card identity cannot change.")
        self.spec=spec;impact=" · High-impact approval" if spec.high_impact else "";self.name_label.configure(text=spec.name);self.version_label.configure(text=f"Official · v{spec.version} · {spec.preferred_mode.value.title()}");self.description_label.configure(text=spec.description);self.state_label.configure(text=f"Capabilities: {spec.capability_count}{impact}\nState: {spec.lifecycle_status}",text_color=self.theme["error"] if spec.high_impact else self.theme["gold"]);self.privacy_label.configure(text=spec.privacy_note)
        wanted=card_actions(spec)
        for name,button in self.buttons.items():
            if name not in wanted:
                if focused_within(button):safe_focus(self)
                button.grid_remove()
        for index,name in enumerate(wanted):
            button=self.buttons.get(name)
            if button is None:
                button=ctk.CTkButton(self.bar,text=name,width=82,fg_color=self.theme["red"] if name not in {"Details","Focus"} else self.theme["gold_dark"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],command=lambda n=name:self.action_callback(n,self.plugin_id));self.buttons[name]=button
            button.grid(row=0,column=index,padx=3)
        self.actions=wanted

class AddonsCenter(ctk.CTkToplevel):
    def __init__(self,parent,theme,manager,window_host,on_close=None,destination_chooser=None):
        super().__init__(parent);self.theme=theme;self.manager=manager;self.window_host=window_host;self.on_close=on_close;self.destination_chooser=destination_chooser or (lambda:filedialog.askdirectory(parent=self,title="Choose template export destination"));self.cards={};self.status_message="";self.title(f"{METADATA.application_name} — Add-ons Center");self.configure(fg_color=theme["bg"]);self.minsize(980,650);self.geometry(self._center(1180,780));self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(2,weight=1);self.protocol("WM_DELETE_WINDOW",self.close)
        ctk.CTkLabel(self,text="⚙ ADD-ONS CENTER ⚙",font=("Times New Roman",28,"bold"),text_color=theme["gold"]).grid(row=0,column=0,sticky="ew",padx=18,pady=(16,6))
        row=ctk.CTkFrame(self,fg_color="transparent");row.grid(row=1,column=0,sticky="ew",padx=18,pady=5);row.grid_columnconfigure(0,weight=1);self.search=ctk.CTkEntry(row,placeholder_text="Search available and installed addons",fg_color=theme["terminal_bg"],border_color=theme["gold_dark"],text_color=theme["text"]);self.search.grid(row=0,column=0,sticky="ew",padx=(0,8));ctk.CTkButton(row,text="Apply",width=90,fg_color=theme["red"],hover_color=theme["red_hover"],command=self.refresh).grid(row=0,column=1)
        self.card_area=ctk.CTkScrollableFrame(self,fg_color=theme["panel"],border_width=1,border_color=theme["border"]);self.card_area.grid(row=2,column=0,sticky="nsew",padx=18,pady=8);self.card_area.bind("<Configure>",lambda _e:self._layout())
        self.footer=ctk.CTkLabel(self,text="Discovery never installs, trusts, approves, enables, loads, or runs an addon.",text_color=theme["gold"],anchor="w",wraplength=1050);self.footer.grid(row=3,column=0,sticky="ew",padx=18,pady=(2,12));self.callbacks=PendingCallbackOwner(self);self.unsubscribe=manager.subscribe(lambda _e,_p:self.callbacks.schedule(0,self.refresh));self.refresh()
    def _center(self,w,h):sw=self.winfo_screenwidth();sh=self.winfo_screenheight();w=min(w,sw);h=min(h,sh);return f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}"
    def _layout(self):
        columns=2 if self.card_area.winfo_width()>=900 else 1
        for index,card in enumerate(self.cards.values()):card.grid(row=index//columns,column=index%columns,sticky="nsew",padx=8,pady=8)
        for column in range(2):self.card_area.grid_columnconfigure(column,weight=1 if column<columns else 0)
    def refresh(self):
        if not widget_exists(self):return
        query=self.search.get().casefold() if hasattr(self,"search") else "";specs={}
        for item in self.manager.official():
            spec=card_spec(item,self.manager,self.window_host)
            if query and query not in (spec.name+spec.plugin_id+spec.description).casefold():continue
            specs[spec.plugin_id]=spec
        for plugin_id in tuple(self.cards):
            if plugin_id not in specs:
                card=self.cards.pop(plugin_id)
                if focused_within(card):safe_focus(self.search)
                card.destroy()
        ordered={}
        for plugin_id,spec in specs.items():
            card=self.cards.get(plugin_id)
            if card is None:card=AddonCard(self.card_area,self.theme,spec,self.action)
            else:card.update_spec(spec)
            ordered[plugin_id]=card
        self.cards=ordered
        self._layout();self.footer.configure(text=self.status_message or f"{len(self.cards)} official addons · Every lifecycle transition remains explicit.")
    def _panel_id(self,plugin_id):return next((c.contribution_id for c in self.manager.registry.by_plugin(plugin_id) if c.contribution_type=="pentest-panel"),"")
    def action(self,name,plugin_id):
        item=self.manager.catalog.get(plugin_id,self.manager.records) if self.manager.catalog else None
        if name=="Details" and item:messagebox.showinfo(item.manifest.name,f"{item.manifest.description}\n\nCapabilities: {', '.join(item.manifest.requested_capabilities) or 'None'}\n\n{item.manifest.caution_text}",parent=self)
        elif name=="Install" and item:self._result(self.manager.install_official(plugin_id,item.package_digest))
        elif name=="Trust":
            manifest=self.manager.records[plugin_id][2];digest=self.manager.records[plugin_id][1].package_digest
            confirmed=messagebox.askyesno("Trust Zero-Capability Addon",f"Addon: {manifest.name}\nVersion: {manifest.version}\nPackage digest: {digest}\n\nThis addon requests zero capabilities. Trust is bound only to this exact digest. Trusting does not enable, load, or open it.\n\nTrust this package?",parent=self)
            self._result(self.manager.trust_zero_capability(plugin_id,confirmed))
        elif name=="Permissions":
            manifest=self.manager.records[plugin_id][2];confirmed=not bool(set(manifest.requested_capabilities)&HIGH_IMPACT) or messagebox.askyesno("Approve Addon Permissions","Approve the displayed capabilities for this exact package digest?",parent=self);self._result(self.manager.approve(plugin_id,manifest.requested_capabilities,confirmed))
        elif name=="Enable":self._result(self.manager.enable(plugin_id))
        elif name=="Load":self._result(self.manager.load(plugin_id))
        elif name in {"Open","Focus"}:
            cid=self._panel_id(plugin_id);window=self.window_host.open(cid);self.refresh()
            if window is None:self.footer.configure(text=self.window_host.errors.get(cid,"Addon window could not be opened."),text_color=self.theme["error"])
        elif name=="Unload":self._result(self.manager.unload(plugin_id))
        else:
            action=next((v for v in item.manifest.addon_ui.get("catalog_actions",()) if v.get("label")==name),None) if item else None
            if action and action.get("kind")=="export-template":
                destination=self.destination_chooser()
                if destination:
                    result=self.manager.catalog.export_template(plugin_id,action["action_id"],destination,item.package_digest)
                    self.status_message=(f"Exported {result.file_count} files ({result.total_bytes} bytes) to {result.path}. Source digest: {result.source_digest}. The copy was not installed or executed." if result.ok else result.error);self.footer.configure(text_color=self.theme["success"] if result.ok else self.theme["error"]);self.refresh()
    def _result(self,result):self.status_message="Operation complete." if result.ok else (result.error or "Operation failed.");self.footer.configure(text_color=self.theme["success"] if result.ok else self.theme["error"]);self.refresh()
    def close(self):
        if self.unsubscribe:self.unsubscribe();self.unsubscribe=None
        self.callbacks.cancel_all()
        safe_focus(self.master)
        if self.on_close:self.on_close()
        self.destroy()
