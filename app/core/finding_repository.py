"""Safe case-local finding repository with append-only history."""
from __future__ import annotations
import json,uuid
from dataclasses import dataclass,replace
from pathlib import Path
from app.core.assessment_scope import now
from app.core.security_finding import SecurityFinding
@dataclass(frozen=True,slots=True)
class FindingResult:
    ok:bool;finding:SecurityFinding|None=None;findings:tuple[SecurityFinding,...]=();warnings:tuple[str,...]=();error:str|None=None;path:str|None=None
class FindingRepository:
    def __init__(self,case_root,timeline=None):self.root=Path(case_root).resolve();self.directory=self.root/"findings";self.history_path=self.directory/"history.jsonl";self.timeline=timeline;self._findings={}
    def _safe(self,path):
        p=Path(path).resolve()
        if p!=self.root and self.root not in p.parents:raise ValueError("Path escapes the case workspace.")
        return p
    def _path(self,fid):
        if not fid or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in fid):raise ValueError("Invalid finding ID.")
        return self._safe(self.directory/f"{fid}.json")
    def _history(self,action,finding,details=None):
        self.directory.mkdir(parents=True,exist_ok=True);record={"timestamp":now(),"action":action,"finding_id":finding.finding_id,"finding_digest":finding.digest,"details":dict(details or {})}
        with self.history_path.open("a",encoding="utf-8") as f:f.write(json.dumps(record,sort_keys=True)+"\n")
    def _save(self,finding,overwrite=False):
        path=self._path(finding.finding_id);self.directory.mkdir(parents=True,exist_ok=True)
        if path.exists() and not overwrite:raise FileExistsError("Finding already exists.")
        path.write_text(json.dumps(finding.to_dict(),indent=2,sort_keys=True),encoding="utf-8");self._findings[finding.finding_id]=finding;return path
    def load(self):
        try:
            self.directory.mkdir(parents=True,exist_ok=True);self._findings={p.stem:SecurityFinding.from_dict(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(self.directory.glob("*.json"))};return FindingResult(True,findings=self.list())
        except (OSError,ValueError,TypeError) as exc:return FindingResult(False,error=str(exc))
    def create(self,finding):
        try:path=self._save(finding);self._history("created",finding);return FindingResult(True,finding,path=str(path),warnings=self.duplicates(finding))
        except (OSError,ValueError) as exc:return FindingResult(False,error=str(exc))
    def update(self,finding,previous_status=None):
        if finding.finding_id not in self._findings:return FindingResult(False,error="Finding was not found.")
        try:self._save(finding,True);self._history("updated",finding,{"previous_status":previous_status or ""});return FindingResult(True,finding,warnings=self.duplicates(finding))
        except (OSError,ValueError) as exc:return FindingResult(False,error=str(exc))
    def duplicate(self,finding_id):
        source=self._findings.get(finding_id)
        return self.create(replace(source,finding_id=str(uuid.uuid4()),title=f"Copy of {source.title}",status="draft",discovered_timestamp=now(),modified_timestamp=now())) if source else FindingResult(False,error="Finding was not found.")
    def archive(self,finding_id):
        source=self._findings.get(finding_id)
        return self.update(source.updated(status="closed"),source.status.value) if source else FindingResult(False,error="Finding was not found.")
    def delete(self,finding_id,confirmed=False):
        if not confirmed:return FindingResult(False,error="Explicit deletion confirmation is required.")
        source=self._findings.get(finding_id)
        if not source:return FindingResult(False,error="Finding was not found.")
        try:self._history("deleted",source);self._path(finding_id).unlink();del self._findings[finding_id];return FindingResult(True)
        except OSError as exc:return FindingResult(False,error=str(exc))
    def list(self):return tuple(sorted(self._findings.values(),key=lambda f:(f.severity.value,f.title.casefold(),f.finding_id)))
    def get(self,fid):return self._findings.get(fid)
    def search(self,query="",severity="All",status="All",confidence="All",category="",tag="",sort="title"):
        q=query.casefold();items=[f for f in self._findings.values() if (severity=="All" or f.severity.value==severity) and (status=="All" or f.status.value==status) and (confidence=="All" or f.confidence.value==confidence) and (not category or f.category==category) and (not tag or tag in f.tags) and (not q or q in (f.title+f.summary+f.detailed_description+f.component_location).casefold())]
        key={"severity":lambda f:f.severity.value,"status":lambda f:f.status.value,"modified":lambda f:f.modified_timestamp}.get(sort,lambda f:f.title.casefold());return tuple(sorted(items,key=key))
    def duplicates(self,finding):
        return tuple(f"Possible duplicate: {f.finding_id}" for f in self._findings.values() if f.finding_id!=finding.finding_id and (f.title.casefold()==finding.title.casefold() or (finding.component_location and f.component_location==finding.component_location)))
    def validate_relationships(self,finding,evidence_ids=(),event_ids=(),note_ids=(),script_ids=()):return {"evidence":tuple(sorted(set(finding.evidence_ids)-set(evidence_ids))),"events":tuple(sorted(set(finding.timeline_event_ids)-set(event_ids))),"notes":tuple(sorted(set(finding.related_note_ids)-set(note_ids))),"scripts":tuple(sorted(set(finding.related_script_profile_ids)-set(script_ids)))}
    def relate(self,finding_id,*,evidence_ids=None,event_ids=None,note_ids=None,script_ids=None):
        finding=self.get(finding_id)
        if not finding:return FindingResult(False,error="Finding was not found.")
        updated=finding.updated(evidence_ids=tuple(evidence_ids) if evidence_ids is not None else finding.evidence_ids,timeline_event_ids=tuple(event_ids) if event_ids is not None else finding.timeline_event_ids,related_note_ids=tuple(note_ids) if note_ids is not None else finding.related_note_ids,related_script_profile_ids=tuple(script_ids) if script_ids is not None else finding.related_script_profile_ids)
        return self.update(updated,finding.status.value)
    def history(self,fid=None):
        if not self.history_path.exists():return ()
        records=tuple(json.loads(line) for line in self.history_path.read_text(encoding="utf-8").splitlines() if line.strip());return tuple(r for r in records if not fid or r["finding_id"]==fid)
    def export_json(self,path,findings=None):
        try:p=self._safe(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps([f.to_dict() for f in (findings or self.list())],indent=2,sort_keys=True),encoding="utf-8");return FindingResult(True,path=str(p))
        except (OSError,ValueError) as exc:return FindingResult(False,error=str(exc))
    def import_json(self,path):
        try:return tuple(self.create(SecurityFinding.from_dict(v)) for v in json.loads(self._safe(path).read_text(encoding="utf-8")))
        except (OSError,ValueError,TypeError) as exc:return (FindingResult(False,error=str(exc)),)
