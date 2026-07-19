"""Responsive Gothic Android Network Workspace embedded in Pentest."""
from __future__ import annotations
import json
import customtkinter as ctk
from app.core.worker import BackgroundWorker

class NetworkWorkspacePanel(ctk.CTkFrame):
    SECTIONS=("Overview","Proxy","Capture","Events","Restore")
    def __init__(self,parent,theme,proxy_workflow,capture_manager,event_ingestor,log_callback,open_scripts,confirm):
        super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.proxy=proxy_workflow;self.capture=capture_manager;self.ingestor=event_ingestor;self.log=log_callback;self.open_scripts=open_scripts;self.confirm=confirm;self.device=None;self.target=None;self._plan=None
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1);self._header();self._tabs();self.ingestor.add_listener(lambda e:self.after(0,self.render_events))
    def _button(self,p,text,cmd,r,c,warning=False):
        b=ctk.CTkButton(p,text=text,command=cmd,fg_color=self.theme["red"] if warning else self.theme["gold_dark"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold"],height=28);b.grid(row=r,column=c,sticky="ew",padx=3,pady=3);return b
    def _entry(self,p,placeholder):return ctk.CTkEntry(p,placeholder_text=placeholder,fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"],placeholder_text_color=self.theme["muted"])
    def _text(self,p,row):t=ctk.CTkTextbox(p,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_width=1,border_color=self.theme["border"],wrap="word",scrollbar_button_color=self.theme["gold_dark"],scrollbar_button_hover_color=self.theme["red_hover"]);t.grid(row=row,column=0,sticky="nsew",padx=7,pady=5);return t
    def _header(self):
        h=ctk.CTkFrame(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["gold_dark"]);h.grid(row=0,column=0,sticky="ew",padx=5,pady=4);h.grid_columnconfigure(0,weight=1)
        self.status=ctk.CTkLabel(h,text="Device: none · Target: none · Proxy: inactive · Capture: idle · Events: 0",text_color=self.theme["gold"],anchor="w",wraplength=720);self.status.grid(row=0,column=0,sticky="ew",padx=8)
        self._button(h,"Refresh",self.refresh_current,0,1);self._button(h,"Open Script Studio",self.open_scripts,0,2);self._button(h,"Restore Network Changes",self.restore_all,0,3,True)
        self.warning=ctk.CTkLabel(h,text="No action executes automatically. Certificate trust and TLS pinning remain separate.",text_color=self.theme["error"],anchor="w",wraplength=900);self.warning.grid(row=1,column=0,columnspan=4,sticky="ew",padx=8,pady=(0,4))
    def _tabs(self):
        self.workspace=ctk.CTkTabview(self,fg_color=self.theme["panel"],segmented_button_fg_color=self.theme["panel_alt"],segmented_button_selected_color=self.theme["red"],segmented_button_selected_hover_color=self.theme["red_hover"],segmented_button_unselected_color=self.theme["panel_alt"],segmented_button_unselected_hover_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.workspace.grid(row=1,column=0,sticky="nsew",padx=5,pady=(0,5));self.tabs={n:self.workspace.add(n) for n in self.SECTIONS}
        for tab in self.tabs.values():tab.configure(fg_color=self.theme["bg"]);tab.grid_columnconfigure(0,weight=1);tab.grid_rowconfigure(1,weight=1)
        self._overview();self._proxy();self._capture();self._events();self._restore()
    def _overview(self):
        p=self.tabs["Overview"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew")
        for i,(n,c) in enumerate((("Configure Proxy",lambda:self.workspace.set("Proxy")),("Start Capture",lambda:self.workspace.set("Capture")),("Open Events",lambda:self.workspace.set("Events")),("Open Script Studio",self.open_scripts),("Restore Changes",lambda:self.workspace.set("Restore")))):bar.grid_columnconfigure(i,weight=1);self._button(bar,n,c,0,i)
        self.overview=self._text(p,1)
    def _proxy(self):
        p=self.tabs["Proxy"];form=ctk.CTkFrame(p,fg_color=self.theme["panel_alt"]);form.grid(row=0,column=0,sticky="ew");form.grid_columnconfigure(2,weight=1)
        self.workflow=ctk.CTkComboBox(form,values=["Physical Device","Emulator","ADB Reverse","Custom"],state="readonly",fg_color=self.theme["terminal_bg"],button_color=self.theme["red"],button_hover_color=self.theme["red_hover"],dropdown_fg_color=self.theme["panel_alt"],dropdown_hover_color=self.theme["red"],text_color=self.theme["text"]);self.workflow.grid(row=0,column=0,padx=3);self.host=self._entry(form,"Proxy host");self.host.insert(0,"127.0.0.1");self.host.grid(row=0,column=1,sticky="ew",padx=3);self.port=self._entry(form,"Port");self.port.insert(0,"8080");self.port.grid(row=0,column=2,sticky="ew",padx=3)
        for i,(n,c,w) in enumerate((("Diagnose Host",self.diagnose,False),("Inspect Device",self.inspect_proxy,False),("Generate Plan",self.generate_plan,False),("Apply Plan",self.apply_plan,True),("Clear Proxy",self.clear_proxy,True),("Restore Original",self.restore_proxy,True))):self._button(form,n,c,1,i,w)
        self.proxy_view=self._text(p,1)
    def _capture(self):
        p=self.tabs["Capture"];bar=ctk.CTkFrame(p,fg_color=self.theme["panel_alt"]);bar.grid(row=0,column=0,sticky="ew");self.destination=self._entry(bar,"Local PCAP destination");self.destination.grid(row=0,column=0,columnspan=3,sticky="ew",padx=3);bar.grid_columnconfigure(0,weight=1)
        self._button(bar,"Preview",self.preview_capture,0,3);self._button(bar,"Start",self.start_capture,0,4,True);self._button(bar,"Stop",self.stop_capture,0,5,True);self._button(bar,"Cancel",self.cancel_capture,0,6,True);self.capture_view=self._text(p,1)
    def _events(self):
        p=self.tabs["Events"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self.event_search=self._entry(bar,"Search host, URL, method, status, payload");self.event_search.grid(row=0,column=0,sticky="ew",padx=3);self._button(bar,"Apply",self.render_events,0,1);self._button(bar,"Pause Display",self.toggle_pause,0,2);self._button(bar,"Clear Display",self.clear_events,0,3);self.event_view=self._text(p,1)
    def _restore(self):
        p=self.tabs["Restore"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self._button(bar,"Restore All",self.restore_all,0,1,True);self.restore_view=self._text(p,1)
    def set_selected_device(self,device):
        serial=getattr(device,"serial","") or ""
        if serial!=getattr(self.device,"serial",""):self.capture.disconnect(getattr(self.device,"serial","") or "");self.proxy.proxy_manager.select(serial)
        self.device=device;self.refresh()
    def set_selected_target(self,target):self.target=target;self.refresh()
    def _run(self,fn,callback):BackgroundWorker(fn,callback=lambda v:self.after(0,callback,v)).start()
    def diagnose(self):self._run(lambda:self.proxy.readiness(self.host.get(),self.port.get()),lambda r:self._show(self.proxy_view,"\n".join(t.display_label for t in r.tools) if r.ok else r.error))
    def inspect_proxy(self):self._run(self.proxy.proxy_manager.inspect,lambda r:self._show(self.proxy_view,json.dumps(r.value,default=lambda x:x.to_dict(),indent=2) if r.ok else r.error))
    def generate_plan(self):
        try:self._plan=self.proxy.build_plan(self.workflow.get(),self.host.get(),self.port.get());self._show(self.proxy_view,self._plan.display_text+"\n\n"+"\n".join(self._plan.guidance))
        except (ValueError,TypeError) as exc:self._show(self.proxy_view,str(exc))
    def apply_plan(self):
        if not self._plan:self._show(self.proxy_view,"Generate and review a plan first.");return
        if self.confirm("Apply Network Plan",self._plan.display_text+"\n\nApply these visible commands to the selected device?"):self._run(lambda:self.proxy.apply(self._plan,True),lambda r:self._result(self.proxy_view,r))
    def clear_proxy(self):
        if self.confirm("Clear Device Proxy","Clear Android global HTTP proxy on the selected device?"):self._run(lambda:self.proxy.proxy_manager.clear_proxy(True),lambda r:self._result(self.proxy_view,r))
    def restore_proxy(self):
        if self.confirm("Restore Device Proxy","Restore the exact originally captured proxy value?"):self._run(lambda:self.proxy.proxy_manager.restore_proxy(True),lambda r:self._result(self.proxy_view,r))
    def preview_capture(self):
        from app.core.network_models import PacketCaptureConfig
        c=PacketCaptureConfig(getattr(self.device,"serial","") or "",getattr(self.target,"identifier","") or "",local_destination=self.destination.get());r=self.capture.preview(c);self._show(self.capture_view," ".join(r.preview))
    def start_capture(self):
        from app.core.network_models import PacketCaptureConfig
        c=PacketCaptureConfig(getattr(self.device,"serial","") or "",getattr(self.target,"identifier","") or "",local_destination=self.destination.get())
        if self.confirm("Start Bounded Capture","Start a visible 30-second bounded capture for the selected device?"):self._run(lambda:self.capture.start(c,True),lambda r:self._result(self.capture_view,r))
    def stop_capture(self):self._run(self.capture.stop,lambda r:self._result(self.capture_view,r))
    def cancel_capture(self):self._run(self.capture.cancel,lambda r:self._result(self.capture_view,r))
    def render_events(self):self._show(self.event_view,"\n\n".join(e.display_text+"\n"+json.dumps(e.to_dict(),indent=2,default=str) for e in self.ingestor.filter(search=self.event_search.get())))
    def toggle_pause(self):self.ingestor.paused=not self.ingestor.paused;self.refresh()
    def clear_events(self):self.event_view.delete("1.0","end")
    def restore_all(self):
        if self.confirm("Restore SUS-ADB Network Changes","Restore only Network Workspace-owned proxy and mapping changes?"):self._run(lambda:self.proxy.restore_all(True),lambda r:self.refresh())
    def refresh_current(self):self.refresh()
    def refresh(self):
        self.status.configure(text=f"Device: {getattr(self.device,'serial','None')} · Target: {getattr(self.target,'identifier','None')} · Proxy changes: {len(self.proxy.proxy_manager.owned_changes())} · Capture: {self.capture.state.value} · Events: {len(self.ingestor.events)} · Dropped: {self.ingestor.dropped}")
        self._show(self.overview,"Host readiness is diagnostic only.\nProxy configured: device state only\nProxy reachable: diagnose the explicit listener\nCertificate trusted: manual verification required\nTLS pinning bypassed: never automatic\n\n"+self.proxy.proxy_manager.guidance())
        self._show(self.restore_view,"\n\n".join(getattr(x,"display_label",str(x)) for x in self.proxy.proxy_manager.owned_changes()) or "No unresolved SUS-ADB network changes.")
    def _show(self,w,text):w.delete("1.0","end");w.insert("1.0",str(text or ""))
    def _result(self,w,r):self._show(w,str(getattr(r,"value",None)) if getattr(r,"ok",False) else getattr(r,"error",r));self.refresh()
    def cleanup(self):self.capture.shutdown();self.ingestor.close()
