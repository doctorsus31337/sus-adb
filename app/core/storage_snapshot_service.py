"""Bounded local storage snapshots with deterministic manifests and comparisons."""
from __future__ import annotations
import hashlib,json,os,shutil
from dataclasses import dataclass
from pathlib import Path
from app.core.storage_models import DifferenceStatus,StorageDifference,StorageSnapshot
from app.core.pentest_event import EventCategory,PentestEvent

@dataclass(frozen=True,slots=True)
class SnapshotResult:
 ok:bool;value:object=None;error:str|None=None;path:str|None=None

class StorageSnapshotService:
 def __init__(self,timeline_provider=lambda:None,evidence_provider=lambda:None,session_provider=lambda:None,max_files=5000,max_total_size=500_000_000):self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.session_provider=session_provider;self.max_files=max_files;self.max_total_size=max_total_size;self.cancelled=False;self.snapshots=[]
 def cancel(self):self.cancelled=True
 def create(self,sources,destination,device_serial="",target_identifier="",max_files=None,max_total_size=None):
  if device_serial:
   session=self.session_provider()
   if not session or not session.permits("storage-inspection"):return SnapshotResult(False,error="Active storage-inspection scope is required for a device-bound snapshot.")
   if session.scope.device_serial!=device_serial or session.scope.package_identifier!=target_identifier:return SnapshotResult(False,error="Selected device/package does not match active scope.")
  selected=tuple(Path(p).expanduser().resolve() for p in sources);dest=Path(destination).expanduser().resolve();max_files=min(max_files or self.max_files,self.max_files);max_total=min(max_total_size or self.max_total_size,self.max_total_size)
  if not selected:return SnapshotResult(False,error="Select at least one explicit source.")
  if dest.exists():return SnapshotResult(False,error="Snapshot destination exists; overwrite is forbidden.")
  if any(not p.exists() for p in selected):return SnapshotResult(False,error="A selected source does not exist.")
  self.cancelled=False;manifest=[];total=0
  try:
   dest.mkdir(parents=True)
   for root in selected:
    candidates=(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else (root,)
    for src in candidates:
     if self.cancelled:return SnapshotResult(False,error="Snapshot cancelled.")
     if src.is_symlink():continue
     resolved=src.resolve()
     if root.is_dir() and root not in resolved.parents:continue
     rel=Path(root.name)/(src.relative_to(root) if root.is_dir() else Path(src.name));target=(dest/rel).resolve()
     if dest not in target.parents:return SnapshotResult(False,error="Snapshot path traversal was rejected.")
     size=src.stat().st_size;total+=size
     if len(manifest)+1>max_files or total>max_total:return SnapshotResult(False,error="Snapshot file-count or total-size limit exceeded.")
     target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target);digest=hashlib.sha256(target.read_bytes()).hexdigest();manifest.append({"path":rel.as_posix(),"size":size,"mtime":src.stat().st_mtime,"sha256":digest})
   manifest.sort(key=lambda x:x["path"]);manifest_path=dest/"manifest.json";text=json.dumps(manifest,indent=2,sort_keys=True);manifest_path.write_text(text,encoding="utf-8");digest=hashlib.sha256(text.encode()).hexdigest();snapshot=StorageSnapshot(device_serial,target_identifier,tuple(str(p) for p in selected),str(dest),len(manifest),total,str(manifest_path),digest);self.snapshots.append(snapshot);self._event("Storage snapshot created",snapshot.display_label,target_identifier);return SnapshotResult(True,snapshot,str(manifest_path))
  except OSError as exc:return SnapshotResult(False,error=str(exc))
 @staticmethod
 def _manifest(snapshot):return {x["path"]:x for x in json.loads(Path(snapshot.manifest_path).read_text(encoding="utf-8"))}
 def compare(self,old,new):
  try:
   a=self._manifest(old);b=self._manifest(new);items=[]
   for path in sorted(set(a)|set(b)):
    x,y=a.get(path),b.get(path);status=DifferenceStatus.ADDED if x is None else DifferenceStatus.REMOVED if y is None else DifferenceStatus.UNCHANGED if x["sha256"]==y["sha256"] else DifferenceStatus.MODIFIED;items.append(StorageDifference(path,status,x["sha256"] if x else "",y["sha256"] if y else "",x["size"] if x else 0,y["size"] if y else 0))
   return SnapshotResult(True,tuple(items))
  except (OSError,ValueError,KeyError,TypeError) as exc:return SnapshotResult(False,error=str(exc))
 def add_to_evidence(self,snapshot,session=None):
  if not session or not session.permits("evidence-collection"):return SnapshotResult(False,error="Evidence-collection scope is required.")
  store=self.evidence_provider();r=store.import_file(snapshot.manifest_path,title=f"Storage snapshot {snapshot.snapshot_id} manifest",device_serial=snapshot.device_serial,target_identifier=snapshot.target_identifier) if store else None;return SnapshotResult(bool(r and r.ok),r.item if r and r.ok else None,getattr(r,"error","No active evidence store."))
 def cleanup(self):self.cancel();return True
 def _event(self,title,description,target):
  timeline=self.timeline_provider()
  if timeline:timeline.append(PentestEvent(EventCategory.STORAGE,"storage-explorer",title,description,related_target_identifier=target))
