"""Responsive Gothic Runtime Explorer using the shared Frida runtime."""
from __future__ import annotations

import json
from tkinter import filedialog, messagebox
import customtkinter as ctk

from app.core.runtime_explorer_models import HookTarget, RuntimeHookSpec
from app.core.worker import BackgroundWorker


class RuntimeExplorerPanel(ctk.CTkFrame):
    SECTIONS=("Classes","Native","Hook Builder","Active Hooks","Events")
    def __init__(self,parent,theme,service,log_callback,open_scripts_callback,confirm_callback=None):
        super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.service=service;self.log=log_callback;self.open_scripts=open_scripts_callback;self.confirm=confirm_callback or(lambda title,text:messagebox.askyesno(title,text,parent=self));self.device=None;self.target=None;self.selected_class=None;self.selected_method=None;self.selected_field=None;self.selected_module=None;self.selected_symbol=None;self.paused=False
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1);self._header();self._workspace();self.service.add_listener(self._queue_event);self._sync()
    def _button(self,p,text,cmd,row=0,col=0,danger=False):
        b=ctk.CTkButton(p,text=text,command=cmd,fg_color=self.theme["error"] if danger else self.theme["red"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold_dark"],height=29);b.grid(row=row,column=col,sticky="ew",padx=3,pady=3);return b
    def _entry(self,p,placeholder=""):return ctk.CTkEntry(p,placeholder_text=placeholder,fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"],placeholder_text_color=self.theme["muted"])
    def _combo(self,p,values):
        x=ctk.CTkComboBox(p,values=values,state="readonly",fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],button_color=self.theme["red"],button_hover_color=self.theme["red_hover"],dropdown_fg_color=self.theme["panel_alt"],dropdown_hover_color=self.theme["red"],text_color=self.theme["text"],dropdown_text_color=self.theme["text"]);x.set(values[0]);return x
    def _text(self,p,row=0,col=0,wrap="word"):
        x=ctk.CTkTextbox(p,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_width=1,border_color=self.theme["border"],font=("Consolas",10),wrap=wrap,scrollbar_button_color=self.theme["gold_dark"],scrollbar_button_hover_color=self.theme["red_hover"]);x.grid(row=row,column=col,sticky="nsew",padx=4,pady=4);return x
    def _header(self):
        h=ctk.CTkFrame(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["gold_dark"]);h.grid(row=0,column=0,sticky="ew",padx=4,pady=3);self.status={}
        fields=(("device","Device"),("target","Target"),("python","Python"),("java","Java"),("server","Server"),("host","Host"),("match","Versions"),("runtime","Runtime"),("hooks","Hooks"),("scope","Scope"))
        for col,(key,title) in enumerate(fields):
            h.grid_columnconfigure(col,weight=1);box=ctk.CTkFrame(h,fg_color="transparent");box.grid(row=0,column=col,sticky="ew",padx=2);ctk.CTkLabel(box,text=title,text_color=self.theme["muted"],font=("Segoe UI",8,"bold")).pack();label=ctk.CTkLabel(box,text="None",text_color=self.theme["gold"],font=("Consolas",8,"bold"),wraplength=78);label.pack(fill="x");self.status[key]=label
        controls=ctk.CTkFrame(h,fg_color="transparent");controls.grid(row=1,column=0,columnspan=10,sticky="ew");controls.grid_columnconfigure(0,weight=1);self.warning=ctk.CTkLabel(controls,text="Select a device and target. Discovery is read-only and never auto-loads hooks.",text_color=self.theme["gold"],anchor="w",wraplength=650);self.warning.grid(row=0,column=0,sticky="ew",padx=5)
        self._button(controls,"Refresh Current View",self.refresh_current,0,1);self._button(controls,"Open Script Studio",self.open_scripts,0,2);self._button(controls,"Unload All Explorer Hooks",self.unload_all,0,3,True)
    def _workspace(self):
        self.workspace=ctk.CTkTabview(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["border"],segmented_button_fg_color=self.theme["panel_alt"],segmented_button_selected_color=self.theme["red"],segmented_button_selected_hover_color=self.theme["red_hover"],segmented_button_unselected_color=self.theme["panel_alt"],segmented_button_unselected_hover_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.workspace.grid(row=1,column=0,sticky="nsew",padx=4,pady=3);self.tabs={name:self.workspace.add(name) for name in self.SECTIONS}
        for tab in self.tabs.values():tab.configure(fg_color=self.theme["bg"]);tab.grid_rowconfigure(0,weight=1);tab.grid_columnconfigure(0,weight=1)
        self._classes();self._native();self._builder();self._active();self._events()
    def _classes(self):
        t=self.tabs["Classes"];root=ctk.CTkFrame(t,fg_color="transparent");root.grid(row=0,column=0,sticky="nsew");root.grid_rowconfigure(1,weight=1);root.grid_columnconfigure(0,weight=2);root.grid_columnconfigure(1,weight=3)
        bar=ctk.CTkFrame(root,fg_color="transparent");bar.grid(row=0,column=0,columnspan=2,sticky="ew");bar.grid_columnconfigure(1,weight=1);self._button(bar,"Refresh Classes",self.refresh_classes,0,0);self.class_search=self._entry(bar,"Search classes");self.class_search.grid(row=0,column=1,sticky="ew",padx=3);self._button(bar,"Filter",self.render_classes,0,2);self.class_namespace=self._entry(bar,"Namespace prefix");self.class_namespace.grid(row=1,column=0,columnspan=2,sticky="ew",padx=3);self.class_limit=self._entry(bar,"Limit");self.class_limit.grid(row=1,column=2);self.class_limit.insert(0,"250")
        left=ctk.CTkFrame(root,fg_color="transparent");left.grid(row=1,column=0,sticky="nsew");left.grid_rowconfigure(0,weight=1);left.grid_columnconfigure(0,weight=1);self.class_view=self._text(left);self._button(left,"Select First Visible Class",self.select_first_class,1,0);self._button(left,"Copy Class Name",lambda:self.copy(self.selected_class.class_name if self.selected_class else ""),2,0)
        right=ctk.CTkFrame(root,fg_color="transparent");right.grid(row=1,column=1,sticky="nsew");right.grid_rowconfigure(1,weight=1);right.grid_columnconfigure(0,weight=1);actions=ctk.CTkFrame(right,fg_color="transparent");actions.grid(row=0,column=0,sticky="ew");actions.grid_columnconfigure(0,weight=1);self._button(actions,"Load Methods",self.load_methods,0,0);self._button(actions,"Load Fields",self.load_fields,0,1);self.method_search=self._entry(actions,"Method search");self.method_search.grid(row=1,column=0,sticky="ew");self._button(actions,"Apply",self.render_members,1,1);self.member_view=self._text(right,1,0);member_actions=ctk.CTkFrame(right,fg_color="transparent");member_actions.grid(row=2,column=0,sticky="ew");self._button(member_actions,"Select First Method",self.select_first_method,0,0);self._button(member_actions,"Copy Signature",lambda:self.copy(self.selected_method.signature if self.selected_method else ""),0,1);self._button(member_actions,"Send to Hook Builder",self.method_to_builder,0,2)
    def _native(self):
        t=self.tabs["Native"];root=ctk.CTkFrame(t,fg_color="transparent");root.grid(row=0,column=0,sticky="nsew");root.grid_rowconfigure(1,weight=1);root.grid_columnconfigure(0,weight=2);root.grid_columnconfigure(1,weight=3)
        bar=ctk.CTkFrame(root,fg_color="transparent");bar.grid(row=0,column=0,columnspan=2,sticky="ew");bar.grid_columnconfigure(1,weight=1);self._button(bar,"Refresh Modules",self.refresh_modules,0,0);self.module_search=self._entry(bar,"Search modules and paths");self.module_search.grid(row=0,column=1,sticky="ew");self._button(bar,"Filter",self.render_modules,0,2)
        left=ctk.CTkFrame(root,fg_color="transparent");left.grid(row=1,column=0,sticky="nsew");left.grid_rowconfigure(0,weight=1);left.grid_columnconfigure(0,weight=1);self.module_view=self._text(left);self._button(left,"Select First Visible Module",self.select_first_module,1,0);self._button(left,"Copy Module Path",lambda:self.copy(self.selected_module.path if self.selected_module else ""),2,0)
        right=ctk.CTkFrame(root,fg_color="transparent");right.grid(row=1,column=1,sticky="nsew");right.grid_rowconfigure(1,weight=1);right.grid_columnconfigure(0,weight=1);bar2=ctk.CTkFrame(right,fg_color="transparent");bar2.grid(row=0,column=0,sticky="ew");bar2.grid_columnconfigure(1,weight=1);self._button(bar2,"Load Exports",self.load_exports,0,0);self.export_search=self._entry(bar2,"Search symbols");self.export_search.grid(row=0,column=1,sticky="ew");self._button(bar2,"Filter",self.render_exports,0,2);self.export_view=self._text(right,1,0);export_actions=ctk.CTkFrame(right,fg_color="transparent");export_actions.grid(row=2,column=0,sticky="ew");self._button(export_actions,"Select First Symbol",self.select_first_symbol,0,0);self._button(export_actions,"Copy Symbol",lambda:self.copy(self.selected_symbol.symbol_name if self.selected_symbol else ""),0,1);self._button(export_actions,"Send to Hook Builder",self.symbol_to_builder,0,2)
    def _check(self,p,text,row,col,default=True):
        v=ctk.BooleanVar(value=default);w=ctk.CTkCheckBox(p,text=text,variable=v,fg_color=self.theme["red"],hover_color=self.theme["red_hover"],border_color=self.theme["gold_dark"],text_color=self.theme["text"]);w.grid(row=row,column=col,sticky="w",padx=4,pady=3);return v
    def _builder(self):
        t=self.tabs["Hook Builder"];root=ctk.CTkFrame(t,fg_color="transparent");root.grid(row=0,column=0,sticky="nsew");root.grid_columnconfigure(1,weight=1);root.grid_rowconfigure(5,weight=1)
        self.hook_type=self._combo(root,["Java Method","Native Export"]);self.hook_type.grid(row=0,column=0,padx=3);self.hook_owner=self._entry(root,"Selected class/module");self.hook_owner.grid(row=0,column=1,sticky="ew");self.hook_member=self._entry(root,"Selected method/symbol");self.hook_member.grid(row=0,column=2);self.hook_overload=self._entry(root,"Overload JSON array");self.hook_overload.grid(row=1,column=1,sticky="ew")
        self.hook_overload.grid(row=1,column=0,sticky="ew");self.script_name=self._entry(root,"Generated script name");self.script_name.grid(row=1,column=1,columnspan=2,sticky="ew");self.script_name.insert(0,"runtime-hook")
        observation=ctk.CTkFrame(root,fg_color="transparent");observation.grid(row=2,column=0,columnspan=3,sticky="ew");self.log_args=self._check(observation,"Log arguments",0,0);self.log_return=self._check(observation,"Log return",0,1);self.log_exceptions=self._check(observation,"Log exceptions",0,2);self.java_stack=self._check(observation,"Java stack",0,3,False);self.native_stack=self._check(observation,"Native backtrace",0,4,False)
        settings=ctk.CTkFrame(root,fg_color="transparent");settings.grid(row=3,column=0,columnspan=3,sticky="ew");settings.grid_columnconfigure(4,weight=1);self.rate=self._entry(settings,"Rate limit");self.rate.grid(row=0,column=0);self.rate.insert(0,"0");self.preview_length=self._entry(settings,"Preview length");self.preview_length.grid(row=0,column=1);self.preview_length.insert(0,"512");self.mode=self._combo(settings,["observation-only","replace-argument","replace-return","throw-exception"]);self.mode.grid(row=0,column=2);self.argument_index=self._entry(settings,"Argument index / exception class");self.argument_index.grid(row=0,column=3);self.replacement=self._entry(settings,"Replacement JSON / message");self.replacement.grid(row=0,column=4,sticky="ew")
        self.classification=ctk.CTkLabel(root,text="Classification: Read-only · Scope: runtime-inspection",text_color=self.theme["gold"],anchor="w",wraplength=800);self.classification.grid(row=4,column=0,columnspan=3,sticky="ew",padx=5)
        self.preview=self._text(root,5,0,"none");self.preview.grid(columnspan=3);self.preview.configure(state="disabled")
        actions=ctk.CTkFrame(root,fg_color="transparent");actions.grid(row=6,column=0,columnspan=3,sticky="ew");
        for i,(name,cmd) in enumerate((("Generate Preview",self.generate_preview),("Copy Generated Script",self.copy_preview),("Save to Script Library",self.save_preview),("Open in Script Studio",self.open_preview),("Load Hook",self.load_hook),("Clear Builder",self.clear_builder))):actions.grid_columnconfigure(i,weight=1);self._button(actions,name,cmd,0,i,name=="Load Hook").configure(width=105)
    def _active(self):
        t=self.tabs["Active Hooks"];t.grid_rowconfigure(0,weight=1);self.active_view=self._text(t);bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=1,column=0,sticky="ew");self._button(bar,"Unload Selected",self.unload_selected,0,0,True);self._button(bar,"Unload All",self.unload_all,0,1,True);self._button(bar,"Open Source in Script Studio",self.open_active,0,2);self._button(bar,"Copy Hook ID",lambda:self.copy(next(iter(self.service.active),"")),0,3)
    def _events(self):
        t=self.tabs["Events"];t.grid_rowconfigure(1,weight=1);bar=ctk.CTkFrame(t,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(3,weight=1);self.event_type=self._combo(bar,["All","discovery","method-enter","method-leave","exception","native-enter","native-leave","stack","warning","error","lifecycle"]);self.event_type.grid(row=0,column=0);self.event_severity=self._combo(bar,["All","info","warning","error"]);self.event_severity.grid(row=0,column=1);self.event_hook=self._entry(bar,"Hook ID");self.event_hook.grid(row=0,column=2);self.event_search=self._entry(bar,"Search events");self.event_search.grid(row=0,column=3,sticky="ew");self._button(bar,"Apply",self.render_events,0,4);self.event_view=self._text(t,1,0);self.event_count=ctk.CTkLabel(t,text="0 events · Dropped 0",text_color=self.theme["gold"]);self.event_count.grid(row=2,column=0,sticky="w");actions=ctk.CTkFrame(t,fg_color="transparent");actions.grid(row=3,column=0,sticky="ew");names=(("Pause Display",self.toggle_pause),("Clear Display",self.clear_events),("Copy Selected",lambda:self.copy(self.event_view.get("1.0","end-1c"))),("Export All JSONL",self.export_events),("Add Selected to Evidence",self.add_selected_evidence),("Add All to Evidence",lambda:self.add_evidence(self.service.events)))
        for i,(name,cmd) in enumerate(names):actions.grid_columnconfigure(i%3,weight=1);self._button(actions,name,cmd,i//3,i%3)
    def set_selected_device(self,device):self.device=device;self.service.select(getattr(device,"serial","") if device else "",self.target);self._clear_stale();self._sync()
    def set_selected_target(self,target):self.target=target;self.service.select(getattr(self.device,"serial","") if self.device else "",target);self._clear_stale();self._sync()
    def _clear_stale(self):self.selected_class=self.selected_method=self.selected_field=self.selected_module=self.selected_symbol=None;self._set(self.class_view,"");self._set(self.member_view,"");self._set(self.module_view,"");self._set(self.export_view,"");self.render_active()
    def _sync(self):
        available=self.service.runtime.adapter.availability();diagnosis=self.service.runtime.last_diagnosis;session=self.service.session_provider();values={"device":getattr(self.device,"serial","None"),"target":getattr(self.target,"identifier",None) or getattr(self.target,"name","None"),"python":(available.value or {}).get("version","Missing") if available.ok else "Missing","java":"Yes" if self.service.discovery.java_available else "No" if self.service.discovery.java_available is False else "Unknown","server":getattr(diagnosis,"server_version","Unknown") or "Unknown","host":(available.value or {}).get("version","Unknown") if available.ok else "Missing","match":"Mismatch" if self.service.runtime.version_warning else "Match" if diagnosis and diagnosis.versions_match else "Unknown","runtime":self.service.runtime.state.value,"hooks":str(len(self.service.active)),"scope":session.state.value if session else "None"}
        for key,value in values.items():self.status[key].configure(text=value)
    def _set(self,w,text):w.configure(state="normal");w.delete("1.0","end");w.insert("1.0",str(text));
    def _run(self,title,fn,done):
        self.warning.configure(text=f"{title}…",text_color=self.theme["gold"]);BackgroundWorker(fn,callback=lambda result:self.after(0,self._done,title,result,done)).start()
    def _done(self,title,result,done):
        if getattr(result,"ok",False):done(result.value);self.warning.configure(text=f"{title} complete. Discovery and generated hooks remain unloaded until explicitly requested.",text_color=self.theme["success"]);self.log(f"[RUNTIME EXPLORER] {title} complete.")
        else:self.warning.configure(text=getattr(result,"error",None) or "Operation failed.",text_color=self.theme["error"]);self.log(f"[RUNTIME EXPLORER ERROR] {getattr(result,'error','Operation failed.')}")
        self._sync()
    def refresh_current(self):getattr(self,{"Classes":"refresh_classes","Native":"refresh_modules","Active Hooks":"render_active","Events":"render_events"}.get(self.workspace.get(),"generate_preview"))()
    def refresh_classes(self):self._run("Java class discovery",self.service.discovery.enumerate_java_classes,lambda _:self.render_classes())
    def render_classes(self):
        try:limit=int(self.class_limit.get())
        except ValueError:limit=250
        items=self.service.discovery.search_java_classes(self.class_search.get(),self.class_namespace.get(),limit);self.visible_classes=items;self._set(self.class_view,"\n".join(item.display_label for item in items))
    def select_first_class(self):self.selected_class=self.visible_classes[0] if getattr(self,"visible_classes",()) else None;self._set(self.member_view,self.selected_class.display_label if self.selected_class else "No class selected.")
    def load_methods(self):
        if self.selected_class:self._run("Java method discovery",lambda:self.service.discovery.enumerate_java_methods(self.selected_class.class_name),lambda _:self.render_members())
    def load_fields(self):
        if self.selected_class:self._run("Java field discovery",lambda:self.service.discovery.enumerate_java_fields(self.selected_class.class_name),lambda _:self.render_members())
    def render_members(self):
        if not self.selected_class:return
        q=self.method_search.get().casefold();self.visible_methods=tuple(item for item in self.service.discovery.methods.get(self.selected_class.class_name,()) if not q or q in item.signature.casefold());fields=self.service.discovery.fields.get(self.selected_class.class_name,());self._set(self.member_view,"METHODS\n"+"\n".join(item.display_label for item in self.visible_methods)+"\n\nFIELDS\n"+"\n".join(item.display_label for item in fields))
    def select_first_method(self):self.selected_method=self.visible_methods[0] if getattr(self,"visible_methods",()) else None
    def method_to_builder(self):
        if not self.selected_method:return
        self.workspace.set("Hook Builder");self.hook_type.set("Java Method");self._replace(self.hook_owner,self.selected_method.declaring_class);self._replace(self.hook_member,self.selected_method.method_name);self._replace(self.hook_overload,json.dumps(self.selected_method.argument_types))
    def refresh_modules(self):self._run("Native module discovery",self.service.discovery.enumerate_native_modules,lambda _:self.render_modules())
    def render_modules(self):self.visible_modules=self.service.discovery.search_modules(self.module_search.get());self._set(self.module_view,"\n\n".join(item.display_label for item in self.visible_modules))
    def select_first_module(self):self.selected_module=self.visible_modules[0] if getattr(self,"visible_modules",()) else None;self._set(self.export_view,self.selected_module.display_label if self.selected_module else "No module selected.")
    def load_exports(self):
        if self.selected_module:self._run("Native export discovery",lambda:self.service.discovery.enumerate_native_exports(self.selected_module.module_name),lambda _:self.render_exports())
    def render_exports(self):
        if not self.selected_module:return
        self.visible_exports=self.service.discovery.search_exports(self.selected_module.module_name,self.export_search.get());self._set(self.export_view,"\n".join(item.display_label for item in self.visible_exports))
    def select_first_symbol(self):self.selected_symbol=self.visible_exports[0] if getattr(self,"visible_exports",()) else None
    def symbol_to_builder(self):
        if not self.selected_symbol:return
        self.workspace.set("Hook Builder");self.hook_type.set("Native Export");self._replace(self.hook_owner,self.selected_symbol.module_name);self._replace(self.hook_member,self.selected_symbol.symbol_name);self._replace(self.hook_overload,"[]")
    def _replace(self,w,text):w.delete(0,"end");w.insert(0,text)
    def _spec(self):
        java=self.hook_type.get()=="Java Method";mode=self.mode.get();changing=mode!="observation-only";mod={}
        if changing:
            if mode=="throw-exception":mod={"mode":mode,"exceptionClass":self.argument_index.get(),"message":self.replacement.get()}
            else:mod={"mode":mode,"value":json.loads(self.replacement.get())}
            if mode=="replace-argument":mod["argumentIndex"]=int(self.argument_index.get())
        return RuntimeHookSpec(HookTarget.JAVA_METHOD if java else HookTarget.NATIVE_EXPORT,self.hook_owner.get(),self.hook_member.get(),tuple(json.loads(self.hook_overload.get() or "[]")),{"logArguments":self.log_args.get(),"logReturn":self.log_return.get(),"logExceptions":self.log_exceptions.get(),"javaStack":self.java_stack.get(),"nativeBacktrace":self.native_stack.get(),"rateLimit":self.rate.get(),"maxPreview":self.preview_length.get()},mod,self.script_name.get() or "runtime-hook",changing,selected_target=getattr(self.target,"identifier",None) or getattr(self.target,"name","") if self.target else "")
    def generate_preview(self):
        try:result=self.service.generate(self._spec())
        except (ValueError,TypeError,json.JSONDecodeError) as exc:self.warning.configure(text=f"Invalid builder value: {exc}",text_color=self.theme["error"]);return
        if result.ok:self.preview.configure(state="normal");self._set(self.preview,result.value.source);self.preview.configure(state="disabled");spec=self.service.preview_spec;self.classification.configure(text=f"Classification: {spec.classification.title()} · Scope: {spec.required_scope_category}\n{spec.caution}",text_color=self.theme["error"] if spec.changes_runtime else self.theme["gold"])
        else:self.warning.configure(text=result.error,text_color=self.theme["error"])
    def copy_preview(self):self.copy(self.preview.get("1.0","end-1c"))
    def save_preview(self):self._done("Save generated hook",self.service.save_preview(),lambda _:None)
    def open_preview(self):self._done("Open generated hook",self.service.open_in_script_studio(),lambda _:None)
    def load_hook(self):
        spec=self.service.preview_spec
        if not spec:self.warning.configure(text="Generate and review a preview first.",text_color=self.theme["error"]);return
        if not self.confirm("Load Runtime Hook",f"Load the exact visible {spec.classification} hook for {spec.owner_name}!{spec.member_name}?\n\n{spec.caution}"):return
        self._run("Load runtime hook",lambda:self.service.load_preview(True),lambda _:self.render_active())
    def clear_builder(self):
        for item in (self.hook_owner,self.hook_member,self.hook_overload,self.replacement,self.argument_index):self._replace(item,"")
        self.service.preview=self.service.preview_spec=self.service.saved_descriptor=None;self.preview.configure(state="normal");self._set(self.preview,"");self.preview.configure(state="disabled")
    def render_active(self):self._set(self.active_view,"\n\n".join(f"{item.spec.display_label}\nLoaded: {item.loaded_at} · Events: {item.event_count}\nLast error: {item.last_error or 'None'}\n{item.spec.caution}" for item in self.service.list_active()));self._sync()
    def unload_selected(self):
        hook_id=next(iter(self.service.active),None)
        if hook_id:self._run("Unload runtime hook",lambda:self.service.unload(hook_id),lambda _:self.render_active())
    def unload_all(self):self.service.unload_all();self.render_active()
    def open_active(self):
        item=next(iter(self.service.active.values()),None)
        if item:self.service.saved_descriptor=item.descriptor;self.open_preview()
    def _queue_event(self,event):self.after(0,self._accept_event,event)
    def _accept_event(self,event):
        if not self.paused:self.render_events()
        self.render_active()
    def render_events(self):
        if self.paused:return
        q=self.event_search.get().casefold();kind=self.event_type.get();severity=self.event_severity.get();hook=self.event_hook.get().strip();items=tuple(item for item in self.service.events if (kind=="All" or item.event_type.value==kind) and (severity=="All" or item.severity==severity) and (not hook or item.hook_id==hook) and (not q or q in item.display_text.casefold()));self.visible_events=items;self._set(self.event_view,"\n\n".join(item.display_text+"\n"+json.dumps(item.to_dict(),indent=2,default=str) for item in items));self.event_count.configure(text=f"{len(items)} shown / {len(self.service.events)} collected · Dropped {self.service.dropped}")
    def toggle_pause(self):self.paused=not self.paused
    def clear_events(self):self.service.events.clear();self.render_events()
    def export_events(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension=".jsonl")
        if path:self._done("Export runtime events",self.service.export_jsonl(path),lambda _:None)
    def add_selected_evidence(self):self.add_evidence(self.visible_events[-1:] if getattr(self,"visible_events",()) else ())
    def add_evidence(self,events):self._done("Add runtime evidence",self.service.add_evidence(events),lambda _:None)
    def copy(self,text):
        if text:self.clipboard_clear();self.clipboard_append(text)
    def cleanup(self):self.service.remove_listener(self._queue_event);return self.service.cleanup()
