"""Responsive Gothic Storage & Data Explorer embedded in Pentest."""
from __future__ import annotations
import json
from pathlib import Path
import customtkinter as ctk
from app.core.worker import BackgroundWorker

class StorageWorkspacePanel(ctk.CTkFrame):
 SECTIONS=("Overview","Files","Preferences","Databases","Providers","Snapshots")
 def __init__(self,parent,theme,storage,preferences,sqlite,providers,snapshots,exports,log,open_adb,open_scripts,confirm):
  super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.storage=storage;self.preferences=preferences;self.sqlite=sqlite;self.providers=providers;self.snapshots=snapshots;self.exports=exports;self.log=log;self.open_adb=open_adb;self.open_scripts=open_scripts;self.confirm=confirm;self.device=None;self.target=None;self.selected_location=None
  self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1);self._header();self._tabs();self.refresh()
 def _button(self,p,text,cmd,r,c,warning=False):b=ctk.CTkButton(p,text=text,command=cmd,fg_color=self.theme["red"] if warning else self.theme["gold_dark"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold"],height=28);b.grid(row=r,column=c,sticky="ew",padx=3,pady=3);return b
 def _entry(self,p,placeholder):return ctk.CTkEntry(p,placeholder_text=placeholder,fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"],placeholder_text_color=self.theme["muted"])
 def _text(self,p,row):t=ctk.CTkTextbox(p,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_width=1,border_color=self.theme["border"],wrap="word",scrollbar_button_color=self.theme["gold_dark"],scrollbar_button_hover_color=self.theme["red_hover"]);t.grid(row=row,column=0,sticky="nsew",padx=7,pady=5);return t
 def _header(self):
  h=ctk.CTkFrame(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["gold_dark"]);h.grid(row=0,column=0,sticky="ew",padx=5,pady=4);h.grid_columnconfigure(0,weight=1);self.status=ctk.CTkLabel(h,text="Device: none · Target: none · Access: explicit · Preferences: 0 · Databases: closed · Snapshots: 0",text_color=self.theme["gold"],anchor="w",wraplength=760);self.status.grid(row=0,column=0,sticky="ew",padx=8);self._button(h,"Refresh",self.refresh_locations,0,1);self._button(h,"Open ADB Files",self.open_adb,0,2);self._button(h,"Open Script Studio",self.open_scripts,0,3);self.warning=ctk.CTkLabel(h,text="No automatic extraction, reveal, decryption, modification, or upload.",text_color=self.theme["error"],anchor="w",wraplength=900);self.warning.grid(row=1,column=0,columnspan=4,sticky="ew",padx=8,pady=(0,4))
 def _tabs(self):
  self.workspace=ctk.CTkTabview(self,fg_color=self.theme["panel"],segmented_button_fg_color=self.theme["panel_alt"],segmented_button_selected_color=self.theme["red"],segmented_button_selected_hover_color=self.theme["red_hover"],segmented_button_unselected_color=self.theme["panel_alt"],segmented_button_unselected_hover_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.workspace.grid(row=1,column=0,sticky="nsew",padx=5,pady=(0,5));self.tabs={n:self.workspace.add(n) for n in self.SECTIONS}
  for tab in self.tabs.values():tab.configure(fg_color=self.theme["bg"]);tab.grid_columnconfigure(0,weight=1);tab.grid_rowconfigure(1,weight=1)
  self.views={}
  actions={"Overview":(("Browse App Data",lambda:self.workspace.set("Files")),("Inspect Preferences",lambda:self.workspace.set("Preferences")),("Inspect Databases",lambda:self.workspace.set("Databases")),("Inspect Providers",lambda:self.workspace.set("Providers")),("Create Snapshot",lambda:self.workspace.set("Snapshots"))),"Files":(("Refresh Locations",self.refresh_locations),("Browse Selected",self.browse_selected),("Open in ADB Explorer",self.open_adb)),"Preferences":(("Parse XML",self.parse_preferences),("Reveal Selected",self.reveal_preference),("Export JSON",self.export_preferences)),"Databases":(("Open Read-only",self.open_database),("Inspect Schema",self.inspect_schema),("Execute SELECT",self.execute_select),("Close Database",self.sqlite.close)),"Providers":(("List Providers",self.list_providers),("Preview Query",self.preview_provider),("Execute Query",self.execute_provider)),"Snapshots":(("Create Snapshot",self.create_snapshot),("Cancel",self.snapshots.cancel),("Compare Last Two",self.compare_snapshots))}
  for name in self.SECTIONS:
   p=self.tabs[name];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew")
   for i,(label,cmd) in enumerate(actions[name]):bar.grid_columnconfigure(i,weight=1);self._button(bar,label,cmd,0,i,label in ("Execute Query","Create Snapshot"))
   if name=="Preferences":self.pref_path=self._entry(bar,"Local SharedPreferences XML");self.pref_path.grid(row=1,column=0,columnspan=len(actions[name]),sticky="ew",padx=3)
   if name=="Databases":self.db_path=self._entry(bar,"Local SQLite database");self.db_path.grid(row=1,column=0,sticky="ew",padx=3);self.query=self._entry(bar,"Read-only SELECT query");self.query.grid(row=1,column=1,columnspan=3,sticky="ew",padx=3)
   if name=="Providers":self.uri=self._entry(bar,"content://authority/path");self.uri.grid(row=1,column=0,columnspan=3,sticky="ew",padx=3)
   if name=="Snapshots":self.snapshot_source=self._entry(bar,"Explicit local source path");self.snapshot_source.grid(row=1,column=0,sticky="ew",padx=3);self.snapshot_dest=self._entry(bar,"New snapshot destination");self.snapshot_dest.grid(row=1,column=1,columnspan=2,sticky="ew",padx=3)
   self.views[name]=self._text(p,1)
 def set_selected_device(self,device):self.device=device;self._sync()
 def set_selected_target(self,target):self.target=target;self._sync()
 def _sync(self):self.storage.select(getattr(self.device,"serial","") or "",getattr(self.target,"identifier","") or "");self.preferences.entries=();self.sqlite.close();self.refresh()
 def _run(self,fn,callback):BackgroundWorker(fn,callback=lambda v:self.after(0,callback,v)).start()
 def refresh_locations(self):self._run(self.storage.discover,lambda r:self._result("Overview",r))
 def browse_selected(self):
  if not self.storage.locations:self._show("Files","Refresh and select an explicit storage location first.");return
  self.selected_location=self.storage.locations[0];self._run(lambda:self.storage.browse(self.selected_location),lambda r:self._result("Files",r))
 def parse_preferences(self):self._run(lambda:self.preferences.parse(self.pref_path.get(),getattr(self.device,"serial","") or "",getattr(self.target,"identifier","") or ""),lambda r:self._result("Preferences",r))
 def reveal_preference(self):
  if not self.preferences.entries:self._show("Preferences","Select a parsed entry first.");return
  r=self.preferences.reveal(self.preferences.entries[0],self.storage.session_provider());self._show("Preferences",json.dumps(r.entries[0].full_value,default=str) if r.ok else r.error)
 def export_preferences(self):self._show("Preferences","Exports require an explicit safe destination through the case workflow; no file was written automatically.")
 def open_database(self):self._run(lambda:self.sqlite.open(self.db_path.get(),target_identifier=getattr(self.target,"identifier","") or "",device_serial=getattr(self.device,"serial","") or ""),lambda r:self._result("Databases",r))
 def inspect_schema(self):self._run(self.sqlite.schema,lambda r:self._result("Databases",r))
 def execute_select(self):self._run(lambda:self.sqlite.select(self.query.get()),lambda r:self._result("Databases",r))
 def list_providers(self):self._run(lambda:self.providers.list(getattr(self.device,"serial","") or "",getattr(self.target,"identifier","") or ""),lambda r:self._result("Providers",r))
 def preview_provider(self):
  from app.core.storage_models import ContentQuerySpec
  r=self.providers.build(getattr(self.device,"serial","") or "",ContentQuerySpec(self.uri.get()));self._show("Providers"," ".join(r.preview) if r.ok else r.error)
 def execute_provider(self):
  from app.core.storage_models import ContentQuerySpec
  spec=ContentQuerySpec(self.uri.get())
  if self.confirm("Execute Read-only Provider Query","Execute the visible bounded content query against the selected device/package?"):self._run(lambda:self.providers.query(getattr(self.device,"serial","") or "",getattr(self.target,"identifier","") or "",spec,True),lambda r:self._result("Providers",r))
 def create_snapshot(self):
  if self.confirm("Create Bounded Snapshot","Copy only the explicit local source into a bounded hashed snapshot?"):self._run(lambda:self.snapshots.create((self.snapshot_source.get(),),self.snapshot_dest.get(),getattr(self.device,"serial","") or "",getattr(self.target,"identifier","") or ""),lambda r:self._result("Snapshots",r))
 def compare_snapshots(self):
  if len(self.snapshots.snapshots)<2:self._show("Snapshots","Create or load two explicit snapshots first.");return
  self._result("Snapshots",self.snapshots.compare(*self.snapshots.snapshots[-2:]))
 def refresh(self):self.status.configure(text=f"Device: {getattr(self.device,'serial','None')} · Target: {getattr(self.target,'identifier','None')} · Access: explicit normal/run-as/root · Preferences: {len(self.preferences.entries)} · Database: {'open' if self.sqlite.connection else 'closed'} · Snapshots: {len(self.snapshots.snapshots)}");self._show("Overview","Public/shared diagnostics may be unrecorded. Private app storage requires active storage-inspection scope. Full sensitive values require explicit reveal and sensitive-data-inspection scope.")
 def _result(self,name,r):
  if getattr(r,"ok",False):value=getattr(r,"value",None) or getattr(r,"entries",None);self._show(name,json.dumps(value,indent=2,default=lambda x:x.to_dict() if hasattr(x,"to_dict") else str(x)))
  else:self._show(name,getattr(r,"error",str(r)))
  self.refresh()
 def _show(self,name,text):w=self.views[name];w.delete("1.0","end");w.insert("1.0",str(text or ""))
 def cleanup(self):self.snapshots.cleanup();self.sqlite.close()
