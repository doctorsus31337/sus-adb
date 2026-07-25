from __future__ import annotations
import customtkinter as ctk
class ApkLaboratoryPanel(ctk.CTkFrame):
 SECTIONS=("Overview","Acquire","Inspect","Decode","Instrument","Build & Sign","Install","Compare")
 def __init__(self,parent,theme,services,log,confirm):
  super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.services=services;self.log=log;self.confirm=confirm;self.device=None;self.target=None;self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1)
  h=ctk.CTkFrame(self,fg_color=theme["panel"],border_width=1,border_color=theme["gold_dark"]);h.grid(row=0,column=0,sticky="ew",padx=5,pady=4);h.grid_columnconfigure(0,weight=1);self.status=ctk.CTkLabel(h,text="Device: none · Package: none · Artifact: none · Tools: optional",text_color=theme["gold"],anchor="w");self.status.grid(row=0,column=0,sticky="ew",padx=8);self.warning=ctk.CTkLabel(h,text="No automatic decode, instrumentation, build, signing, installation, launch, download, or secret persistence.",text_color=theme["error"],anchor="w",wraplength=900);self.warning.grid(row=1,column=0,sticky="ew",padx=8)
  self.workspace=ctk.CTkTabview(self,fg_color=theme["panel"],segmented_button_fg_color=theme["panel_alt"],segmented_button_selected_color=theme["red"],segmented_button_selected_hover_color=theme["red_hover"],segmented_button_unselected_color=theme["panel_alt"],segmented_button_unselected_hover_color=theme["gold_dark"],text_color=theme["text"]);self.workspace.grid(row=1,column=0,sticky="nsew",padx=5,pady=5);self.tabs={n:self.workspace.add(n) for n in self.SECTIONS};self.views={}
  for n,t in self.tabs.items():t.configure(fg_color=theme["bg"]);t.grid_rowconfigure(0,weight=1);t.grid_columnconfigure(0,weight=1);v=ctk.CTkTextbox(t,fg_color=theme["terminal_bg"],text_color=theme["terminal_text"],border_width=1,border_color=theme["border"],wrap="word",scrollbar_button_color=theme["gold_dark"],scrollbar_button_hover_color=theme["red_hover"]);v.grid(row=0,column=0,sticky="nsew",padx=6,pady=6);v.insert("1.0",f"{n}\n\nEvery operation is previewed and explicitly confirmed. Original artifacts are immutable.");self.views[n]=v
 def set_selected_device(self,d):self.device=d;self._sync()
 def set_selected_target(self,t):self.target=t;self._sync()
 def _sync(self):self.status.configure(text=f"Device: {getattr(self.device,'serial','None')} · Package: {getattr(self.target,'identifier','None')} · Artifact: none · Tools: optional")
 def cleanup(self):
  for k in ("decode","build","sign"):
   if k in self.services and hasattr(self.services[k],"cleanup"):self.services[k].cleanup()
