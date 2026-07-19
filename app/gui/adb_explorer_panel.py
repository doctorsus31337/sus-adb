"""Responsive Gothic Advanced ADB Explorer workspace."""
from __future__ import annotations
from pathlib import Path
from tkinter import filedialog,messagebox,simpledialog
import customtkinter as ctk
from app.core.adb_capture_service import ADBCaptureService
from app.core.adb_component_service import ADBComponentService
from app.core.adb_explorer_models import AccessMethod
from app.core.adb_file_service import ADBFileService
from app.core.adb_intent_service import ADBIntentService
from app.core.adb_logcat_manager import ADBLogcatManager
from app.core.adb_package_service import ADBPackageService
from app.core.worker import BackgroundWorker

class ADBExplorerPanel(ctk.CTkFrame):
    SECTIONS=("Packages","Components","Files","Intents","Logcat","Capture")
    def __init__(self,parent,theme,adb,session_provider,timeline_provider,evidence_provider,change_provider,log_callback):
        super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.adb=adb;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.change_provider=change_provider;self.log=log_callback;self.device=None;self.target=None;self.packages=();self.components=();self.current_path="/sdcard";self.current_output="";self.capture_history=[]
        self.package_service=ADBPackageService(adb,session_provider,timeline_provider,change_provider);self.component_service=ADBComponentService(adb);self.intent_service=ADBIntentService(adb,session_provider,timeline_provider);self.file_service=ADBFileService(adb,session_provider,timeline_provider,evidence_provider,change_provider);self.logcat=ADBLogcatManager(adb,callback=self._log_event,evidence_provider=evidence_provider);self.capture=ADBCaptureService(adb,evidence_provider=evidence_provider,session_provider=session_provider)
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1);self._header();self._tabs()
    def _button(self,p,text,cmd,row=0,col=0,danger=False):
        b=ctk.CTkButton(p,text=text,command=cmd,fg_color=self.theme["error"] if danger else self.theme["red"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold_dark"],height=29);b.grid(row=row,column=col,sticky="ew",padx=3,pady=3);return b
    def _entry(self,p,placeholder=""):
        return ctk.CTkEntry(p,placeholder_text=placeholder,fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"],placeholder_text_color=self.theme["muted"])
    def _combo(self,p,values):
        x=ctk.CTkComboBox(p,values=values,state="readonly",fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],button_color=self.theme["red"],button_hover_color=self.theme["red_hover"],dropdown_fg_color=self.theme["panel_alt"],dropdown_hover_color=self.theme["red"],text_color=self.theme["text"],dropdown_text_color=self.theme["text"]);x.set(values[0]);return x
    def _header(self):
        h=ctk.CTkFrame(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["gold_dark"]);h.grid(row=0,column=0,sticky="ew",padx=4,pady=3);h.grid_columnconfigure(7,weight=1);self.status={}
        for col,(key,title) in enumerate((("device","Device"),("target","Target"),("adb","ADB"),("root","Root"),("access","Access"),("case","Assessment"),("logcat","Logcat"),("recording","Recording"))):
            box=ctk.CTkFrame(h,fg_color="transparent");box.grid(row=0,column=col,sticky="ew",padx=3);ctk.CTkLabel(box,text=title,text_color=self.theme["muted"],font=("Segoe UI",9,"bold")).pack();label=ctk.CTkLabel(box,text="None",text_color=self.theme["gold"],font=("Consolas",9,"bold"),wraplength=100);label.pack();self.status[key]=label
        self.warning=ctk.CTkLabel(h,text="Read-only discovery is available after selecting a device. Actions outside a case are not recorded.",text_color=self.theme["gold"],anchor="w",wraplength=750);self.warning.grid(row=1,column=0,columnspan=6,sticky="ew",padx=5)
        self._button(h,"Refresh Current View",self.refresh_current,1,6);self._button(h,"Add Output to Evidence",self.add_output_evidence,1,7)
    def _tabs(self):
        self.workspace=ctk.CTkTabview(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["border"],segmented_button_fg_color=self.theme["panel_alt"],segmented_button_selected_color=self.theme["red"],segmented_button_selected_hover_color=self.theme["red_hover"],segmented_button_unselected_color=self.theme["panel_alt"],segmented_button_unselected_hover_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.workspace.grid(row=1,column=0,sticky="nsew",padx=4,pady=3);self.tabs={n:self.workspace.add(n) for n in self.SECTIONS}
        for tab in self.tabs.values():tab.configure(fg_color=self.theme["bg"]);tab.grid_rowconfigure(1,weight=1);tab.grid_columnconfigure(0,weight=1)
        self._packages();self._components();self._files();self._intents();self._logcat();self._capture()
    def _viewer(self,tab):
        t=ctk.CTkTextbox(tab,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_width=1,border_color=self.theme["border"],font=("Consolas",10),wrap="word",scrollbar_button_color=self.theme["gold_dark"],scrollbar_button_hover_color=self.theme["red_hover"]);t.grid(row=1,column=0,sticky="nsew",padx=5,pady=5);return t
    def _packages(self):
        t=self.tabs["Packages"];bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self.package_search=self._entry(bar,"Search packages");self.package_search.grid(row=0,column=0,sticky="ew",padx=3);self.package_kind=self._combo(bar,["all","user","system"]);self.package_kind.grid(row=0,column=1,padx=3);self._button(bar,"Refresh",self.refresh_packages,0,2)
        for i,(n,c,d) in enumerate((("Install APK",self.install_apk,False),("Uninstall",lambda:self.package_action("uninstall",True),True),("Force Stop",lambda:self.package_action("force-stop"),False),("Clear Data",lambda:self.package_action("clear-data",True),True),("Enable",lambda:self.package_action("enable"),False),("Disable",lambda:self.package_action("disable"),False),("Grant",lambda:self.permission_action("grant"),False),("Revoke",lambda:self.permission_action("revoke"),False))):self._button(bar,n,c,1+i//4,i%4,d)
        self.package_view=self._viewer(t)
    def _components(self):
        t=self.tabs["Components"];bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self.component_search=self._entry(bar,"Search components");self.component_search.grid(row=0,column=0,sticky="ew");self.component_type=self._combo(bar,["All","activity","service","receiver","provider"]);self.component_type.grid(row=0,column=1);self._button(bar,"Discover",self.refresh_components,0,2);self._button(bar,"Open in Intents",lambda:self.workspace.set("Intents"),0,3);self.component_view=self._viewer(t)
    def _files(self):
        t=self.tabs["Files"];bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(1,weight=1);self.access_mode=self._combo(bar,["normal-shell","run-as","root"]);self.access_mode.grid(row=0,column=0);self.remote_path=self._entry(bar);self.remote_path.grid(row=0,column=1,sticky="ew");self.remote_path.insert(0,self.current_path);self._button(bar,"List",self.refresh_files,0,2);self._button(bar,"Up",self.file_up,0,3);self._button(bar,"Pull",self.pull_file,1,0);self._button(bar,"Push",self.push_file,1,1);self._button(bar,"New Directory",self.mkdir,1,2);self._button(bar,"Delete",self.delete_remote,1,3,True);self.file_view=self._viewer(t)
    def _intents(self):
        t=self.tabs["Intents"];bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(1,weight=1);self.intent_operation=self._combo(bar,list(ADBIntentService.OPERATIONS));self.intent_operation.grid(row=0,column=0);self.intent_component=self._entry(bar,"package/class or package");self.intent_component.grid(row=0,column=1,sticky="ew");self.intent_uri=self._entry(bar,"URI / action");self.intent_uri.grid(row=1,column=1,sticky="ew");self._button(bar,"Preview",self.preview_intent,0,2);self._button(bar,"Execute",self.execute_intent,1,2);self.intent_view=self._viewer(t)
    def _logcat(self):
        t=self.tabs["Logcat"];bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(5,weight=1);self._button(bar,"Start",self.start_logcat,0,0);self._button(bar,"Stop",self.stop_logcat,0,1);self._button(bar,"Pause Display",self.pause_logcat,0,2);self._button(bar,"Clear Display",self.clear_logcat,0,3);self._button(bar,"Clear Device",self.clear_device_logcat,0,4,True);self.log_search=self._entry(bar,"Filter text");self.log_search.grid(row=0,column=5,sticky="ew");self.dropped=ctk.CTkLabel(bar,text="Dropped: 0",text_color=self.theme["gold"]);self.dropped.grid(row=0,column=6);self.log_view=self._viewer(t)
    def _capture(self):
        t=self.tabs["Capture"];bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self.capture_path=self._entry(bar,"Output path");self.capture_path.grid(row=0,column=0,sticky="ew");self.duration=self._entry(bar,"Duration (1-180)");self.duration.grid(row=0,column=1);self.duration.insert(0,"15");self._button(bar,"Screenshot",self.screenshot,0,2);self._button(bar,"Start Recording",self.start_recording,0,3);self._button(bar,"Stop Recording",self.stop_recording,0,4,True);self.capture_view=self._viewer(t)
    def set_selected_device(self,device):self.device=device;self.packages=();self.components=();self.stop_logcat();self.stop_recording();self._sync()
    def set_selected_target(self,target):self.target=target;self.packages=();self.components=();self._sync()
    def _sync(self):
        session=self.session_provider();vals={"device":getattr(self.device,"serial","None"),"target":getattr(self.target,"identifier",None) or "None","adb":"Ready" if self.adb.exists() else "Missing","root":"Yes" if getattr(self.device,"root",False) else "No","access":self.access_mode.get() if hasattr(self,"access_mode") else "Normal","case":session.state.value if session else "None","logcat":self.logcat.state.value,"recording":"Active" if self.capture.recording else "Stopped"}
        for k,v in vals.items():self.status[k].configure(text=v)
    def _serial(self):return getattr(self.device,"serial","")
    def _package(self):return getattr(self.target,"identifier",None) or ""
    def _show(self,widget,text):self.current_output=str(text);widget.delete("1.0","end");widget.insert("1.0",self.current_output)
    def _run(self,title,fn,done):
        self.warning.configure(text=f"{title}…",text_color=self.theme["gold"])
        BackgroundWorker(fn,callback=lambda result:self.after(0,self._done,title,result,done)).start()
    def _done(self,title,result,done):
        if getattr(result,"ok",False):done(result);self.log(f"[ADB EXPLORER] {title} complete.");self.warning.configure(text=f"{title} complete.",text_color=self.theme["success"])
        else:self.warning.configure(text=getattr(result,"error",None) or "Operation failed.",text_color=self.theme["error"]);self.log(f"[ADB EXPLORER ERROR] {getattr(result,'error','Operation failed.')}")
        self._sync()
    def refresh_current(self):getattr(self,{"Packages":"refresh_packages","Components":"refresh_components","Files":"refresh_files"}.get(self.workspace.get(),"preview_intent"))()
    def refresh_packages(self):self._run("Package refresh",lambda:self.package_service.list_packages(self._serial(),self.package_kind.get()),lambda r:self._show(self.package_view,"\n".join(p.display_label for p in r.value)))
    def refresh_components(self):self._run("Component discovery",lambda:self.component_service.discover(self._serial(),self._package()),lambda r:self._show(self.component_view,"\n\n".join(f"{c.display_label}\nexported={c.exported} enabled={c.enabled}\nactions={', '.join(c.intent_actions)}" for c in r.value)))
    def refresh_files(self):self.current_path=self.remote_path.get();self._run("Directory listing",lambda:self.file_service.list_directory(self._serial(),self.current_path,AccessMethod(self.access_mode.get()),self._package()),lambda r:self._show(self.file_view,"\n".join(e.display_label+"\n  "+e.remote_path for e in r.value)))
    def file_up(self):
        current=self.remote_path.get();parent=str(Path(current).parent).replace("\\","/");self.remote_path.delete(0,"end");self.remote_path.insert(0,parent);self.refresh_files()
    def preview_intent(self):
        value=self.intent_component.get();op=self.intent_operation.get();kwargs={"component":value} if "/" in value else {"package":value or self._package()};kwargs["uri" if op=="deep-link" else "action"]=self.intent_uri.get();r=self.intent_service.build(self._serial(),op,**kwargs);self._show(self.intent_view," ".join(r.preview) if r.ok else r.error)
    def execute_intent(self):
        if not messagebox.askyesno("Execute Intent","Execute the exact visible ADB intent command?",parent=self):return
        value=self.intent_component.get();op=self.intent_operation.get();kwargs={"component":value} if "/" in value else {"package":value or self._package()};kwargs["uri" if op=="deep-link" else "action"]=self.intent_uri.get();self._run("Intent",lambda:self.intent_service.execute(self._serial(),op,confirmed=True,**kwargs),lambda r:self._show(self.intent_view,r.value))
    def package_action(self,action,typed=False):
        package=self._package()
        if not package:self.warning.configure(text="Select an application target first.",text_color=self.theme["error"]);return
        confirm=simpledialog.askstring("Typed Confirmation",f"Type the full package identifier to confirm {action}:\n{package}",parent=self) if typed else (package if messagebox.askyesno("Confirm",f"Execute {action} for {package}?",parent=self) else "")
        if not confirm:return
        self._run(f"Package {action}",lambda:self.package_service.execute(self._serial(),action,package,confirmed=True,typed_confirmation=confirm),lambda r:self._show(self.package_view,r.value))
    def permission_action(self,action):
        value=simpledialog.askstring("Permission",f"Android permission to {action}:",parent=self)
        if value:self._run(action,lambda:self.package_service.execute(self._serial(),action,self._package(),value,confirmed=True),lambda r:self._show(self.package_view,r.value))
    def install_apk(self):
        path=filedialog.askopenfilename(parent=self,filetypes=(("Android packages","*.apk"),))
        if path and messagebox.askyesno("Install APK",f"Install selected APK on {self._serial()}?",parent=self):self._run("Install APK",lambda:self.package_service.execute(self._serial(),"install",value=path,confirmed=True),lambda r:self._show(self.package_view,r.value))
    def pull_file(self):
        remote=self.remote_path.get();dest=filedialog.asksaveasfilename(parent=self,initialfile=Path(remote).name)
        if dest:self._run("Pull",lambda:self.file_service.pull(self._serial(),remote,dest),lambda r:self._show(self.file_view,r.value))
    def push_file(self):
        src=filedialog.askopenfilename(parent=self)
        if src and messagebox.askyesno("Push File",f"Push {src} to {self.remote_path.get()}?",parent=self):self._run("Push",lambda:self.file_service.push(self._serial(),src,self.remote_path.get(),True,self._package()),lambda r:self._show(self.file_view,r.value))
    def mkdir(self):
        path=simpledialog.askstring("New Directory","Full remote directory path:",parent=self)
        if path:self._run("Create directory",lambda:self.file_service.mutate(self._serial(),"mkdir",self.remote_path.get(),path,AccessMethod(self.access_mode.get()),self._package(),True),lambda r:self.refresh_files())
    def delete_remote(self):
        path=self.remote_path.get();typed=simpledialog.askstring("Delete Remote Path",f"Type the complete remote path to confirm deletion:\n{path}",parent=self)
        if typed:self._run("Remote delete",lambda:self.file_service.mutate(self._serial(),"delete",path,mode=AccessMethod(self.access_mode.get()),package=self._package(),confirmed=True,typed=typed),lambda r:self._show(self.file_view,r.value))
    def start_logcat(self):self._done("Logcat start",self.logcat.start(self._serial(),self._package()),lambda r:None)
    def stop_logcat(self):self.logcat.stop();self._sync()
    def pause_logcat(self):self.logcat.pause_display(not self.logcat.paused);self._sync()
    def clear_logcat(self):self.logcat.clear_display();self._show(self.log_view,"")
    def clear_device_logcat(self):
        if messagebox.askyesno("Clear Device Logcat","Clear the selected device Logcat buffer?",parent=self):self._done("Clear device Logcat",self.logcat.clear_device(True),lambda r:None)
    def _log_event(self,event):self.after(0,self._render_log,event)
    def _render_log(self,event):
        if self.log_search.get().casefold() not in event.display_label.casefold():return
        self.log_view.insert("end",event.display_label+"\n");self.log_view.see("end");self.dropped.configure(text=f"Dropped: {self.logcat.dropped}")
    def screenshot(self):
        dest=self.capture_path.get() or filedialog.asksaveasfilename(parent=self,defaultextension=".png")
        if dest and messagebox.askyesno("Capture Screenshot",f"Capture the visible screen of {self._serial()}?",parent=self):self._run("Screenshot",lambda:self.capture.screenshot(self._serial(),dest,self._package(),confirmed=True),self._capture_done)
    def start_recording(self):
        dest=self.capture_path.get() or filedialog.asksaveasfilename(parent=self,defaultextension=".mp4")
        if dest:
            if not messagebox.askyesno("Start Recording",f"Record the visible screen of {self._serial()} for up to {self.duration.get()} seconds?",parent=self):return
            result=self.capture.start_recording(self._serial(),dest,self.duration.get(),self._package(),confirmed=True);self._done("Recording start",result,lambda r:setattr(self,"record_context",r.value))
    def stop_recording(self):
        if hasattr(self,"record_context"):
            self.capture.stop_recording();self._run("Recording pull",lambda:self.capture.finish_recording(self.record_context),self._capture_done)
        else:self.capture.stop_recording();self._sync()
    def _capture_done(self,result):self.capture_history.append(result.value);self._show(self.capture_view,"\n".join(a.display_label for a in self.capture_history))
    def add_output_evidence(self):
        store=self.evidence_provider();session=self.session_provider()
        if not store or not session or not session.permits("evidence-collection"):self.warning.configure(text="An active case with evidence-collection scope is required.",text_color=self.theme["error"]);return
        result=store.add_command_output("ADB Explorer output",self.current_output,device_serial=self._serial(),target_identifier=self._package());self.warning.configure(text="Output added to evidence." if result.ok else result.error,text_color=self.theme["success"] if result.ok else self.theme["error"])
    def cleanup(self):self.logcat.stop();self.capture.cleanup()
