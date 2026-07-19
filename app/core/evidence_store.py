"""Safe, case-local evidence persistence and deterministic manifests."""
from __future__ import annotations
import hashlib,json,mimetypes,shutil
from dataclasses import dataclass,replace
from pathlib import Path
from app.core.evidence_item import EvidenceItem,EvidenceType,Sensitivity
@dataclass(frozen=True,slots=True)
class EvidenceResult:
    ok: bool; item: EvidenceItem|None=None; items: tuple[EvidenceItem,...]=(); path: str|None=None; error: str|None=None
class EvidenceStore:
    LAYOUT=("timeline","evidence","notes","exports","reports","temporary")
    def __init__(self,workspace_root,case_id): self.workspace_root=Path(workspace_root).resolve(); self.case_id=case_id; self.root=(self.workspace_root/case_id).resolve(); self.metadata_path=self.root/"evidence"/"manifest.json"; self._items=[]
    def _safe(self,path):
        p=(self.root/Path(path)).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        if p!=self.root and self.root not in p.parents: raise ValueError("Path escapes the case workspace.")
        return p
    def create_workspace(self):
        try:
            if self.root.parent!=self.workspace_root: raise ValueError("Invalid case ID.")
            for part in self.LAYOUT: (self.root/part).mkdir(parents=True,exist_ok=True)
            return EvidenceResult(True,path=str(self.root))
        except (OSError,ValueError) as exc:return EvidenceResult(False,error=str(exc))
    @staticmethod
    def digest(data): return hashlib.sha256(data).hexdigest()
    def _persist(self): self.metadata_path.write_text(json.dumps([i.to_dict() for i in sorted(self._items,key=lambda x:x.evidence_id)],indent=2,sort_keys=True),encoding="utf-8")
    def load(self):
        self.create_workspace()
        try:self._items=[EvidenceItem.from_dict(i) for i in json.loads(self.metadata_path.read_text(encoding="utf-8"))] if self.metadata_path.exists() else []; return EvidenceResult(True,items=tuple(self._items))
        except (OSError,ValueError,TypeError) as exc:return EvidenceResult(False,error=str(exc))
    def import_file(self,source,title="",sensitivity=Sensitivity.INTERNAL,**metadata):
        src=Path(source).expanduser().resolve()
        if not src.is_file():return EvidenceResult(False,error="Select an existing evidence file.")
        data=src.read_bytes(); digest=self.digest(data)
        if any(i.sha256==digest for i in self._items):return EvidenceResult(False,error="Duplicate evidence content already exists.")
        try:
            self.create_workspace(); dest=self._safe(Path("evidence")/f"{digest[:12]}-{src.name}"); shutil.copy2(src,dest)
            item=EvidenceItem(metadata.pop("evidence_type",EvidenceType.FILE),title or src.name,dest.relative_to(self.root).as_posix(),digest,len(data),original_source=str(src),mime_type=mimetypes.guess_type(src.name)[0] or "application/octet-stream",sensitivity=sensitivity,**metadata)
            self._items.append(item);self._persist();return EvidenceResult(True,item=item,path=str(dest))
        except (OSError,ValueError,TypeError) as exc:return EvidenceResult(False,error=str(exc))
    def add_text(self,title,text,evidence_type=EvidenceType.NOTE,**metadata):
        data=text.encode();digest=self.digest(data)
        if any(i.sha256==digest for i in self._items):return EvidenceResult(False,error="Duplicate evidence content already exists.")
        try:
            self.create_workspace(); dest=self._safe(Path("evidence")/f"{digest[:12]}.txt");dest.write_bytes(data)
            item=EvidenceItem(evidence_type,title,dest.relative_to(self.root).as_posix(),digest,len(data),mime_type="text/plain",**metadata);self._items.append(item);self._persist();return EvidenceResult(True,item=item,path=str(dest))
        except (OSError,ValueError,TypeError) as exc:return EvidenceResult(False,error=str(exc))
    def add_command_output(self,title,text,**metadata):return self.add_text(title,text,EvidenceType.COMMAND_OUTPUT,**metadata)
    def list(self):return tuple(self._items)
    def search(self,query="",evidence_type="All",sensitivity="All",tag=""):
        q=query.casefold();return tuple(i for i in self._items if (evidence_type=="All" or i.evidence_type.value==evidence_type) and (sensitivity=="All" or i.sensitivity.value==sensitivity) and (not tag or tag in i.tags) and (not q or q in (i.title+i.description+i.original_source+" ".join(i.tags)).casefold()))
    def retrieve(self,item):
        try:p=self._safe(item.stored_path);return EvidenceResult(p.is_file(),item=item,path=str(p),error=None if p.is_file() else "Evidence file is missing.")
        except ValueError as exc:return EvidenceResult(False,error=str(exc))
    def rename_metadata(self,item,title):
        if not title.strip():return EvidenceResult(False,error="Evidence title is required.")
        updated=replace(item,title=title.strip());self._items=[updated if i.evidence_id==item.evidence_id else i for i in self._items];self._persist();return EvidenceResult(True,item=updated)
    def delete(self,item,confirmed=False):
        if not confirmed:return EvidenceResult(False,error="Explicit deletion confirmation is required.")
        try:self._safe(item.stored_path).unlink(missing_ok=True);self._items=[i for i in self._items if i.evidence_id!=item.evidence_id];self._persist();return EvidenceResult(True)
        except (OSError,ValueError) as exc:return EvidenceResult(False,error=str(exc))
    def export_manifest(self,path,markdown=False,selected_ids=None):
        selected=[i for i in self._items if selected_ids is None or i.evidence_id in selected_ids]
        try:
            p=self._safe(path);p.parent.mkdir(parents=True,exist_ok=True)
            text="# Evidence Manifest\n\n"+"\n".join(f"- **{i.title}** — `{i.sha256}` — {i.sensitivity.value}" for i in selected) if markdown else json.dumps([i.to_dict() for i in selected],indent=2,sort_keys=True)
            p.write_text(text,encoding="utf-8");return EvidenceResult(True,path=str(p))
        except (OSError,ValueError) as exc:return EvidenceResult(False,error=str(exc))
