"""Modal Gothic editor for one assessment-scope transaction."""
from __future__ import annotations
import uuid
from datetime import date
import customtkinter as ctk
from app.core.assessment_scope import ACTION_CATEGORIES,AssessmentScope,now
class ScopeDialog(ctk.CTkToplevel):
    def __init__(self,parent,theme,scope=None,device=None,target=None,on_save=None):
        super().__init__(parent);self.theme=theme;self.scope=scope;self.on_save=on_save;self.title("Authorized Assessment Scope");self.geometry("650x680");self.minsize(580,560);self.configure(fg_color=theme["bg"]);self.transient(parent.winfo_toplevel());self.grab_set()
        self.grid_rowconfigure(1,weight=1);self.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(self,text="AUTHORIZED ASSESSMENT SCOPE",text_color=theme["gold"],font=("Times New Roman",22,"bold")).grid(row=0,column=0,pady=(12,5))
        form=ctk.CTkScrollableFrame(self,fg_color=theme["panel"],scrollbar_button_color=theme["gold_dark"],scrollbar_button_hover_color=theme["red_hover"]);form.grid(row=1,column=0,sticky="nsew",padx=12,pady=5);form.grid_columnconfigure(1,weight=1)
        values={"case_name":scope.case_name if scope else "","description":scope.description if scope else "","tester_name":scope.tester_name if scope else "","client_project":scope.client_project if scope else "","authorization_reference":scope.authorization_reference if scope else "","device_serial":scope.device_serial if scope else getattr(device,"serial", ""),"device_model":scope.device_model if scope else getattr(device,"display_name", ""),"target_name":scope.target_name if scope else getattr(target,"name", ""),"package_identifier":scope.package_identifier if scope else getattr(target,"identifier", "") or "","pid":str(scope.pid or "") if scope else str(getattr(target,"pid", "") or ""),"start_date":scope.start_date if scope else date.today().isoformat(),"end_date":scope.end_date or "" if scope else "","notes":scope.notes if scope else ""}
        self.entries={};row=0
        for key,label in (("case_name","Assessment name"),("description","Description"),("tester_name","Tester"),("client_project","Client / Project"),("authorization_reference","Authorization reference / notes"),("device_serial","Selected device serial"),("device_model","Device model"),("target_name","Selected target"),("package_identifier","Package identifier"),("pid","PID"),("start_date","Start date (YYYY-MM-DD)"),("end_date","End date (optional)"),("notes","Scope notes")):
            ctk.CTkLabel(form,text=label+":",text_color=theme["muted"],anchor="w").grid(row=row,column=0,sticky="nw",padx=8,pady=4);entry=ctk.CTkEntry(form,fg_color=theme["terminal_bg"],border_color=theme["gold_dark"],text_color=theme["text"]);entry.grid(row=row,column=1,sticky="ew",padx=8,pady=4);entry.insert(0,values[key]);self.entries[key]=entry;row+=1
        ctk.CTkLabel(form,text="Allowing a category never executes an action. Exclusions always override allowances.",text_color=theme["gold"],wraplength=540).grid(row=row,column=0,columnspan=2,sticky="ew",padx=8,pady=8);row+=1
        self.allowed={};self.excluded={}
        for category in ACTION_CATEGORIES:
            ctk.CTkLabel(form,text=category,text_color=theme["text"],anchor="w").grid(row=row,column=0,sticky="w",padx=8)
            holder=ctk.CTkFrame(form,fg_color="transparent");holder.grid(row=row,column=1,sticky="w")
            allow=ctk.CTkCheckBox(holder,text="Allowed",fg_color=theme["red"],hover_color=theme["red_hover"],border_color=theme["gold_dark"],text_color=theme["text"]);allow.pack(side="left",padx=5)
            exclude=ctk.CTkCheckBox(holder,text="Excluded",fg_color=theme["red"],hover_color=theme["red_hover"],border_color=theme["gold_dark"],text_color=theme["text"]);exclude.pack(side="left",padx=5)
            if scope and category in scope.allowed_actions:allow.select()
            if scope and category in scope.excluded_actions:exclude.select()
            self.allowed[category]=allow;self.excluded[category]=exclude;row+=1
        self.authorization=ctk.CTkCheckBox(form,text="I confirm that I own or have explicit permission to assess this device and target.",fg_color=theme["red"],hover_color=theme["red_hover"],border_color=theme["gold_dark"],text_color=theme["text"]);self.authorization.grid(row=row,column=0,columnspan=2,sticky="w",padx=8,pady=12)
        if scope and scope.authorization_confirmed:self.authorization.select()
        self.message=ctk.CTkLabel(self,text="Authorization is mandatory before a session can start.",text_color=theme["error"],wraplength=600,justify="left",anchor="w");self.message.grid(row=2,column=0,sticky="ew",padx=12,pady=3)
        footer=ctk.CTkFrame(self,fg_color="transparent");footer.grid(row=3,column=0,sticky="ew",padx=12,pady=10);footer.grid_columnconfigure(0,weight=1)
        self._button(footer,"Cancel",self.destroy,1);self._button(footer,"Validate & Save",self.save,2)
    def _button(self,parent,text,command,column):ctk.CTkButton(parent,text=text,command=command,fg_color=self.theme["red"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold_dark"]).grid(row=0,column=column,padx=4)
    def save(self):
        for entry in self.entries.values():entry.configure(border_color=self.theme["gold_dark"])
        try:pid=int(self.entries["pid"].get()) if self.entries["pid"].get().strip() else None
        except ValueError:self._show_errors(("PID must be an integer.",),"pid");return
        scope=AssessmentScope(self.scope.scope_id if self.scope else str(uuid.uuid4()),self.entries["case_name"].get(),self.entries["description"].get(),self.entries["tester_name"].get(),self.entries["client_project"].get(),self.entries["authorization_reference"].get(),bool(self.authorization.get()),self.entries["device_serial"].get(),self.entries["device_model"].get(),self.entries["target_name"].get(),self.entries["package_identifier"].get(),pid,tuple(k for k,v in self.allowed.items() if v.get()),tuple(k for k,v in self.excluded.items() if v.get()),self.entries["start_date"].get(),self.entries["end_date"].get() or None,self.entries["notes"].get(),self.scope.created_at if self.scope else now(),now())
        validation=scope.validate(for_start=True)
        if not validation.valid:
            mapping=(("assessment","case_name"),("tester","tester_name"),("client","client_project"),("authorization","authorization_reference"),("device","device_serial"),("target","package_identifier"),("start date","start_date"),("end date","end_date"));first=next((key for token,key in mapping if any(token in e.casefold() for e in validation.errors)),"case_name");self._show_errors(validation.errors,first);return
        if self.on_save:self.on_save(scope)
        self.destroy()
    def _show_errors(self,errors,first):
        self.message.configure(text="Please correct the following:\n"+"\n".join(f"• {error}" for error in errors));entry=self.entries.get(first)
        if entry:entry.configure(border_color=self.theme["error"],border_width=2);entry.focus_set()
