"""Case-local report exports, hashing, history and evidence verification."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass,replace
from pathlib import Path
from app.core.report_assembler import ReportAssembler
from app.core.report_models import ReportSnapshot
from app.core.report_renderer import ReportRenderer
@dataclass(frozen=True,slots=True)
class ReportExportResult:
    ok:bool;snapshot:ReportSnapshot|None=None;paths:tuple[str,...]=();hashes:dict|None=None;warnings:tuple[str,...]=();error:str|None=None
class ReportExportService:
    def __init__(self,case_root,timeline=None,evidence_store=None):self.root=Path(case_root).resolve();self.reports=self.root/"reports";self.history_path=self.reports/"history.jsonl";self.timeline=timeline;self.evidence_store=evidence_store
    def _safe(self,name):
        p=(self.reports/Path(name)).resolve()
        if p!=self.reports and self.reports not in p.parents:raise ValueError("Report path escapes the case reports directory.")
        return p
    def preview(self,data):return tuple(data.get("limitations",()))
    def snapshot(self,session,profile,data):
        a=ReportAssembler();return ReportSnapshot(Path(session.workspace_path).name,session.scope.digest,session.state.value,profile,tuple(f["finding_id"] for f in data["findings"]),tuple(hashlib.sha256(json.dumps(f,sort_keys=True,default=str).encode()).hexdigest() for f in data["findings"]),a.digest(data["evidence_manifest"]),a.digest(data["timeline"]),len(data["unresolved_environment_changes"]),tuple(data["limitations"]))
    def export(self,session,profile,data,formats=("md","html","json"),basename="assessment-report"):
        try:
            self.reports.mkdir(parents=True,exist_ok=True);renderers={"md":ReportRenderer.markdown,"html":ReportRenderer.html,"json":ReportRenderer.json};paths=[];hashes={}
            for fmt in formats:
                if fmt not in renderers:raise ValueError(f"Unsupported report format: {fmt}")
                p=self._safe(f"{basename}.{fmt}")
                if p.exists():raise FileExistsError(f"Report already exists: {p.name}")
                content=renderers[fmt](data);p.write_text(content,encoding="utf-8");paths.append(str(p));hashes[p.name]=hashlib.sha256(content.encode()).hexdigest()
            snapshot=replace(self.snapshot(session,profile,data),output_paths=tuple(Path(p).relative_to(self.root).as_posix() for p in paths));record={"snapshot":snapshot.to_dict(),"output_hashes":hashes}
            with self.history_path.open("a",encoding="utf-8") as f:f.write(json.dumps(record,sort_keys=True)+"\n")
            return ReportExportResult(True,snapshot,tuple(paths),hashes,tuple(data["limitations"]))
        except (OSError,ValueError) as exc:return ReportExportResult(False,error=str(exc))
    def export_manifest(self,evidence,name="evidence-manifest.json"):
        data=[{"evidence_id":i.evidence_id,"title":i.title,"stored_path":i.stored_path,"sha256":i.sha256,"file_size":i.file_size} for i in sorted(evidence,key=lambda i:i.evidence_id)]
        try:
            p=self._safe(name)
            if p.exists():raise FileExistsError("Evidence manifest already exists.")
            p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8");return ReportExportResult(True,paths=(str(p),),hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()})
        except (OSError,ValueError) as exc:return ReportExportResult(False,error=str(exc))
    def history(self):
        if not self.history_path.exists():return ()
        return tuple(json.loads(line) for line in self.history_path.read_text(encoding="utf-8").splitlines() if line.strip())
    def compare(self,a,b):return {"added":tuple(sorted(set(b.selected_finding_ids)-set(a.selected_finding_ids))),"removed":tuple(sorted(set(a.selected_finding_ids)-set(b.selected_finding_ids))),"changed":a.finding_digests!=b.finding_digests or a.evidence_manifest_digest!=b.evidence_manifest_digest}
    def verify_evidence(self,evidence):
        results={}
        for item in evidence:
            try:p=(self.root/item.stored_path).resolve();results[item.evidence_id]=self.root in p.parents and p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==item.sha256
            except OSError:results[item.evidence_id]=False
        return results
    def add_report_to_evidence(self,path,confirmed=False):
        if not confirmed:return ReportExportResult(False,error="Explicit evidence registration is required.")
        if not self.evidence_store:return ReportExportResult(False,error="No evidence store is available.")
        result=self.evidence_store.import_file(path,title=Path(path).name,evidence_type="report");return ReportExportResult(result.ok,paths=(result.path,) if result.path else (),error=result.error)
