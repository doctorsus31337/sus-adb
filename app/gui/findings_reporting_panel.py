"""Responsive Gothic Findings and Reports workspaces."""
from __future__ import annotations
import json
from dataclasses import replace
import customtkinter as ctk
from app.core.security_finding import SecurityFinding,Severity,Confidence,FindingStatus
from app.core.finding_validator import FindingValidator
from app.core.report_models import ReportProfile
from app.core.report_assembler import ReportAssembler
from app.core.report_renderer import ReportRenderer

class FindingsReportingPanel:
    FINDING_SECTIONS=("Finding List","Editor","Evidence Links","Retest","History")
    REPORT_SECTIONS=("Report Profiles","Builder","Preview","Exports","History")
    def __init__(self,findings_parent,reports_parent,theme,log,confirm):
        self.theme=theme;self.log=log;self.confirm=confirm;self.repository=None;self.export_service=None;self.session=None;self.timeline=None;self.evidence=None;self.notes=None;self.changes=None;self.device=None;self.target=None;self.selected=None;self.profile=ReportProfile("Default Assessment Report");self.report_data=None;self._workers=[]
        self.findings_root=self._root(findings_parent,"Findings");self.reports_root=self._root(reports_parent,"Reports");self.finding_tabs,self.finding_views=self._tabs(self.findings_root,self.FINDING_SECTIONS);self.report_tabs,self.report_views=self._tabs(self.reports_root,self.REPORT_SECTIONS);self._build_findings();self._build_reports();self.refresh()
    def _root(self,parent,title):
        root=ctk.CTkFrame(parent,fg_color=self.theme["bg"],corner_radius=0);root.grid(row=0,column=0,sticky="nsew");root.grid_columnconfigure(0,weight=1);root.grid_rowconfigure(1,weight=1);self.__dict__[title.lower()+"_header"]=ctk.CTkLabel(root,text=f"{title} · No active case",text_color=self.theme["gold"],anchor="w",wraplength=950);self.__dict__[title.lower()+"_header"].grid(row=0,column=0,sticky="ew",padx=8,pady=5);return root
    def _tabs(self,root,names):
        tab=ctk.CTkTabview(root,fg_color=self.theme["panel"],segmented_button_fg_color=self.theme["panel_alt"],segmented_button_selected_color=self.theme["red"],segmented_button_selected_hover_color=self.theme["red_hover"],segmented_button_unselected_color=self.theme["panel_alt"],segmented_button_unselected_hover_color=self.theme["gold_dark"],text_color=self.theme["text"]);tab.grid(row=1,column=0,sticky="nsew",padx=5,pady=5);views={n:tab.add(n) for n in names}
        for v in views.values():v.configure(fg_color=self.theme["bg"]);v.grid_columnconfigure(0,weight=1);v.grid_rowconfigure(1,weight=1)
        return tab,views
    def _button(self,p,text,cmd,row,col):
        b=ctk.CTkButton(p,text=text,command=cmd,fg_color=self.theme["red"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold_dark"],height=30);b.grid(row=row,column=col,sticky="ew",padx=3,pady=3);return b
    def _text(self,p,row=1,readonly=False):
        t=ctk.CTkTextbox(p,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_width=1,border_color=self.theme["border"],wrap="word");t.grid(row=row,column=0,sticky="nsew",padx=7,pady=5)
        if readonly:t.configure(state="disabled")
        return t
    def _set(self,w,text):w.configure(state="normal");w.delete("1.0","end");w.insert("1.0",text);w.configure(state="disabled")
    def _build_findings(self):
        p=self.finding_views["Finding List"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self.search=ctk.CTkEntry(bar,placeholder_text="Search findings",fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.search.grid(row=0,column=0,sticky="ew",padx=3);self._button(bar,"Apply",self.render_findings,0,1);self._button(bar,"Create Finding",self.new_finding,0,2);self.finding_list=self._text(p,1,True)
        p=self.finding_views["Editor"];form=ctk.CTkFrame(p,fg_color="transparent");form.grid(row=0,column=0,sticky="ew");form.grid_columnconfigure(0,weight=1);self.title=ctk.CTkEntry(form,placeholder_text="Finding title",fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.title.grid(row=0,column=0,sticky="ew",padx=3);self.severity=ctk.CTkComboBox(form,values=[v.value for v in Severity],state="readonly",button_color=self.theme["red"],button_hover_color=self.theme["red_hover"],fg_color=self.theme["terminal_bg"],text_color=self.theme["text"]);self.severity.grid(row=0,column=1,padx=3);self.editor=self._text(p,1);actions=ctk.CTkFrame(p,fg_color="transparent");actions.grid(row=2,column=0,sticky="ew");self._button(actions,"Save Draft",self.save_draft,0,0);self._button(actions,"Validate",self.validate,0,1);self._button(actions,"Mark Ready for Review",self.ready,0,2);self.validation=ctk.CTkLabel(p,text="",text_color=self.theme["gold"],anchor="w",wraplength=850);self.validation.grid(row=3,column=0,sticky="ew",padx=7)
        for name in ("Evidence Links","Retest","History"):self.__dict__[name.lower().replace(" ","_")+"_view"]=self._text(self.finding_views[name],1,True)
    def _build_reports(self):
        for name in self.REPORT_SECTIONS:self.__dict__["report_"+name.lower().replace(" ","_")+"_view"]=self._text(self.report_views[name],1,True)
        p=self.report_views["Builder"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Generate Preview",self.generate_preview,0,0)
        p=self.report_views["Exports"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Markdown",lambda:self.export(("md",)),0,0);self._button(bar,"HTML",lambda:self.export(("html",)),0,1);self._button(bar,"JSON",lambda:self.export(("json",)),0,2);self._button(bar,"Export All",lambda:self.export(("md","html","json")),0,3)
    def set_services(self,session,repository=None,export_service=None,timeline=None,evidence=None,notes=None,changes=None):self.session=session;self.repository=repository;self.export_service=export_service;self.timeline=timeline;self.evidence=evidence;self.notes=notes;self.changes=changes;self.refresh()
    def set_selected_device(self,device):self.device=device;self.refresh_header()
    def set_selected_target(self,target):self.target=target;self.refresh_header()
    def refresh_header(self):
        case=self.session.scope.case_name if self.session else "No active case";count=len(self.repository.list()) if self.repository else 0;unresolved=len(self.changes.unresolved()) if self.changes else 0;self.findings_header.configure(text=f"Findings · {case} · {count} total · target {getattr(self.target,'identifier','None')}");self.reports_header.configure(text=f"Reports · {case} · {unresolved} unresolved change(s) · local/offline only")
    def refresh(self):self.refresh_header();self.render_findings();self.render_support();self.render_reports()
    def render_findings(self):
        items=self.repository.search(self.search.get()) if self.repository and hasattr(self,"search") else ();self.selected=self.selected or (items[-1] if items else None);self._set(self.finding_list,"\n\n".join(f.display_label+f"\n{f.summary}\nTarget: {', '.join(f.affected_target_identifiers)}" for f in items) or "No findings. Drafts may be saved with advisory warnings.")
    def render_support(self):
        if not hasattr(self,"history_view"):return
        f=self.selected;self._set(self.evidence_links_view,"No finding selected." if not f else f"Evidence: {', '.join(f.evidence_ids) or 'None'}\nTimeline: {', '.join(f.timeline_event_ids) or 'None'}\nNotes: {', '.join(f.related_note_ids) or 'None'}\nScripts/Profiles: {', '.join(f.related_script_profile_ids) or 'None'}");self._set(self.retest_view,"Retests preserve prior finding history. Select a finding and explicitly save a retest outcome.");self._set(self.history_view,json.dumps(self.repository.history(f.finding_id),indent=2) if f and self.repository else "No history.")
    def new_finding(self):self.selected=None;self.title.delete(0,"end");self.editor.delete("1.0","end");self.finding_tabs.set("Editor")
    def _draft(self):
        target=getattr(self.target,"identifier","") or getattr(self.target,"name","");base=self.selected or SecurityFinding(self.title.get().strip());return base.updated(title=self.title.get().strip(),detailed_description=self.editor.get("1.0","end-1c"),severity=self.severity.get(),status=FindingStatus.DRAFT,affected_target_identifiers=(target,) if target else ())
    def save_draft(self):
        if not self.repository:self.validation.configure(text="Create or open an assessment case before saving.",text_color=self.theme["error"]);return
        draft=self._draft();validation=FindingValidator().validate(draft,evidence_ids=[i.evidence_id for i in self.evidence.list()] if self.evidence else (),event_ids=[e.event_id for e in self.timeline.events()] if self.timeline else (),authorization=bool(self.session and self.session.scope.authorization_confirmed));result=self.repository.update(draft) if self.repository.get(draft.finding_id) else self.repository.create(draft)
        if result.ok:self.selected=draft;self.validation.configure(text="Draft saved. "+" ".join(validation.warnings),text_color=self.theme["gold"]);self.refresh()
        else:self.validation.configure(text=result.error,text_color=self.theme["error"])
    def validate(self):
        v=FindingValidator().validate(self._draft(),authorization=bool(self.session and self.session.scope.authorization_confirmed),for_review=True);self.validation.configure(text="Errors: "+("; ".join(v.errors) or "None")+"\nWarnings: "+("; ".join(v.warnings) or "None")+"\nSuggestions: "+("; ".join(v.suggestions) or "None"),text_color=self.theme["error"] if v.errors else self.theme["gold"])
    def ready(self):
        v=FindingValidator().validate(self._draft(),authorization=bool(self.session and self.session.scope.authorization_confirmed),for_review=True)
        if v.errors:self.validate();return
        if self.selected:self.repository.update(self.selected.updated(status=FindingStatus.NEEDS_REVIEW),self.selected.status.value);self.refresh()
    def _assemble(self):return ReportAssembler().assemble(self.session,self.profile,self.repository.list(),self.timeline.events() if self.timeline else (),self.evidence.list() if self.evidence else (),self.notes.search() if self.notes else (),self.changes.filter() if self.changes else ())
    def generate_preview(self):
        if not self.session:self._set(self.report_preview_view,"No active case. Report generation requires case context.");return
        self.report_data=self._assemble();self._set(self.report_preview_view,ReportRenderer.markdown(self.report_data));self.report_tabs.set("Preview")
    def export(self,formats):
        if not self.export_service or not self.session:return self._set(self.report_exports_view,"No active case export service.")
        if self.report_data is None:self.report_data=self._assemble()
        result=self.export_service.export(self.session,self.profile,self.report_data,formats,basename="assessment-report")
        self._set(self.report_exports_view,("Exported locally:\n"+"\n".join(result.paths)+"\n\nSHA-256:\n"+json.dumps(result.hashes,indent=2)) if result.ok else result.error)
    def render_reports(self):
        if not hasattr(self,"report_report_profiles_view"):return
        self._set(self.report_report_profiles_view,json.dumps(self.profile.to_dict(),indent=2));self._set(self.report_builder_view,"Generate a deterministic preview. Evidence contents are excluded; metadata and hashes are included.");self._set(self.report_history_view,json.dumps(self.export_service.history(),indent=2) if self.export_service else "No report history.")
    def open_findings(self):self.finding_tabs.set("Finding List")
    def open_builder(self):self.report_tabs.set("Builder")
    def cleanup(self):self._workers.clear()
