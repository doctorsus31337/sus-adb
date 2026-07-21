"""Focused non-modal Add-ons Center with explicit lifecycle cards."""
from __future__ import annotations
from tkinter import messagebox
import customtkinter as ctk
from app.plugins.plugin_capabilities import HIGH_IMPACT
from app.plugins.addon_presenter import card_spec

class AddonCard(ctk.CTkFrame):
    def __init__(self,parent,theme,spec,actions):
        super().__init__(parent,fg_color=theme["panel_alt"],border_width=1,border_color=theme["border"],corner_radius=10);self.plugin_id=spec.plugin_id;self.spec=spec;self.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(self,text=spec.name,text_color=theme["gold"],font=theme["header_font"],anchor="w",wraplength=390).grid(row=0,column=0,sticky="ew",padx=12,pady=(10,2))
        ctk.CTkLabel(self,text=f"Official · v{spec.version} · {spec.preferred_mode.value.title()}",text_color=theme["muted"],anchor="w").grid(row=1,column=0,sticky="ew",padx=12)
        ctk.CTkLabel(self,text=spec.description,text_color=theme["text"],anchor="nw",justify="left",wraplength=390,height=54).grid(row=2,column=0,sticky="ew",padx=12,pady=5)
        impact=" · High-impact approval" if spec.high_impact else "";ctk.CTkLabel(self,text=f"Capabilities: {spec.capability_count}{impact}\nState: {spec.lifecycle_status}",text_color=theme["error"] if spec.high_impact else theme["gold"],anchor="w",justify="left").grid(row=3,column=0,sticky="ew",padx=12)
        ctk.CTkLabel(self,text=spec.privacy_note,text_color=theme["muted"],anchor="nw",justify="left",wraplength=390,height=48).grid(row=4,column=0,sticky="ew",padx=12,pady=5)
        bar=ctk.CTkFrame(self,fg_color="transparent");bar.grid(row=5,column=0,sticky="ew",padx=8,pady=(2,10))
        valid={"Available":("Details","Install"),"Permissions Required":("Details","Permissions"),"Installed":("Details","Enable"),"Enabled":("Details","Load"),"Loaded":("Details","Open","Unload"),"Window Open":("Details","Focus","Unload"),"Error":("Details",)}[spec.lifecycle_status]
        for index,name in enumerate(valid):ctk.CTkButton(bar,text=name,width=82,fg_color=theme["red"] if name not in {"Details","Focus"} else theme["gold_dark"],hover_color=theme["red_hover"],text_color=theme["text"],command=lambda n=name:actions(n,spec.plugin_id)).grid(row=0,column=index,padx=3)

class AddonsCenter(ctk.CTkToplevel):
    def __init__(self,parent,theme,manager,window_host,on_close=None):
        super().__init__(parent);self.theme=theme;self.manager=manager;self.window_host=window_host;self.on_close=on_close;self.cards={};self.title("SUS-ADB — Add-ons Center");self.configure(fg_color=theme["bg"]);self.minsize(980,650);self.geometry(self._center(1180,780));self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(2,weight=1);self.protocol("WM_DELETE_WINDOW",self.close)
        ctk.CTkLabel(self,text="⚙ ADD-ONS CENTER ⚙",font=("Times New Roman",28,"bold"),text_color=theme["gold"]).grid(row=0,column=0,sticky="ew",padx=18,pady=(16,6))
        row=ctk.CTkFrame(self,fg_color="transparent");row.grid(row=1,column=0,sticky="ew",padx=18,pady=5);row.grid_columnconfigure(0,weight=1);self.search=ctk.CTkEntry(row,placeholder_text="Search available and installed addons",fg_color=theme["terminal_bg"],border_color=theme["gold_dark"],text_color=theme["text"]);self.search.grid(row=0,column=0,sticky="ew",padx=(0,8));ctk.CTkButton(row,text="Apply",width=90,fg_color=theme["red"],hover_color=theme["red_hover"],command=self.refresh).grid(row=0,column=1)
        self.card_area=ctk.CTkScrollableFrame(self,fg_color=theme["panel"],border_width=1,border_color=theme["border"]);self.card_area.grid(row=2,column=0,sticky="nsew",padx=18,pady=8);self.card_area.bind("<Configure>",lambda _e:self._layout())
        self.footer=ctk.CTkLabel(self,text="Discovery never installs, trusts, approves, enables, loads, or runs an addon.",text_color=theme["gold"],anchor="w",wraplength=1050);self.footer.grid(row=3,column=0,sticky="ew",padx=18,pady=(2,12));self.unsubscribe=manager.subscribe(lambda _e,_p:self.after(0,self.refresh));self.refresh()
    def _center(self,w,h):sw=self.winfo_screenwidth();sh=self.winfo_screenheight();w=min(w,sw);h=min(h,sh);return f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}"
    def _layout(self):
        columns=2 if self.card_area.winfo_width()>=900 else 1
        for index,card in enumerate(self.cards.values()):card.grid(row=index//columns,column=index%columns,sticky="nsew",padx=8,pady=8)
        for column in range(2):self.card_area.grid_columnconfigure(column,weight=1 if column<columns else 0)
    def refresh(self):
        for card in self.cards.values():card.destroy()
        self.cards={};query=self.search.get().casefold() if hasattr(self,"search") else ""
        for item in self.manager.official():
            spec=card_spec(item,self.manager,self.window_host)
            if query and query not in (spec.name+spec.plugin_id+spec.description).casefold():continue
            self.cards[spec.plugin_id]=AddonCard(self.card_area,self.theme,spec,self.action)
        self._layout();self.footer.configure(text=f"{len(self.cards)} official addons · Every lifecycle transition remains explicit.")
    def _panel_id(self,plugin_id):return next((c.contribution_id for c in self.manager.registry.by_plugin(plugin_id) if c.contribution_type=="pentest-panel"),"")
    def action(self,name,plugin_id):
        item=self.manager.catalog.get(plugin_id,self.manager.records) if self.manager.catalog else None
        if name=="Details" and item:messagebox.showinfo(item.manifest.name,f"{item.manifest.description}\n\nCapabilities: {', '.join(item.manifest.requested_capabilities) or 'None'}\n\n{item.manifest.caution_text}",parent=self)
        elif name=="Install" and item:self._result(self.manager.install_official(plugin_id,item.package_digest))
        elif name=="Permissions":
            manifest=self.manager.records[plugin_id][2];confirmed=not bool(set(manifest.requested_capabilities)&HIGH_IMPACT) or messagebox.askyesno("Approve Addon Permissions","Approve the displayed capabilities for this exact package digest?",parent=self);self._result(self.manager.approve(plugin_id,manifest.requested_capabilities,confirmed))
        elif name=="Enable":self._result(self.manager.enable(plugin_id))
        elif name=="Load":self._result(self.manager.load(plugin_id))
        elif name in {"Open","Focus"}:
            cid=self._panel_id(plugin_id);window=self.window_host.open(cid);self.refresh()
            if window is None:self.footer.configure(text=self.window_host.errors.get(cid,"Addon window could not be opened."),text_color=self.theme["error"])
        elif name=="Unload":self._result(self.manager.unload(plugin_id))
    def _result(self,result):self.footer.configure(text="Operation complete." if result.ok else (result.error or "Operation failed."),text_color=self.theme["success"] if result.ok else self.theme["error"]);self.refresh()
    def close(self):
        if self.unsubscribe:self.unsubscribe();self.unsubscribe=None
        if self.on_close:self.on_close()
        self.destroy()
