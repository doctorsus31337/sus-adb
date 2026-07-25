"""Deterministic safe structured exports for Storage Explorer."""
from __future__ import annotations
import csv,json
from dataclasses import asdict,is_dataclass
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True,slots=True)
class ExportResult:
 ok:bool;path:str|None=None;error:str|None=None

class StorageExportService:
 def __init__(self,case_root_provider=lambda:None,session_provider=lambda:None):self.case_root_provider=case_root_provider;self.session_provider=session_provider
 def _path(self,path):
  p=Path(path).expanduser().resolve();root=self.case_root_provider()
  if root:
   root=Path(root).resolve()
   if p!=root and root not in p.parents:raise ValueError("Export path escapes the active case.")
  if p.exists():raise ValueError("Destination exists; overwrite was not authorized.")
  return p
 @staticmethod
 def _value(v):return v.to_dict() if hasattr(v,"to_dict") else asdict(v) if is_dataclass(v) else v
 def metadata(self,device_serial="",target_identifier=""):
  session=self.session_provider();return {"device_serial":device_serial,"target_identifier":target_identifier,"session_id":getattr(session,"session_id",None),"scope_digest":getattr(getattr(session,"scope",None),"digest",None)}
 def json(self,path,kind,items,device_serial="",target_identifier=""):
  try:p=self._path(path);p.parent.mkdir(parents=True,exist_ok=True);payload={"kind":kind,"metadata":self.metadata(device_serial,target_identifier),"items":[self._value(v) for v in items]};p.write_text(json.dumps(payload,indent=2,sort_keys=True,default=str),encoding="utf-8");return ExportResult(True,str(p))
  except (OSError,ValueError,TypeError) as exc:return ExportResult(False,error=str(exc))
 def markdown(self,path,title,items,device_serial="",target_identifier=""):
  try:p=self._path(path);p.parent.mkdir(parents=True,exist_ok=True);meta=self.metadata(device_serial,target_identifier);p.write_text(f"# {title}\n\nDevice: `{meta['device_serial']}`  \nTarget: `{meta['target_identifier']}`\n\n"+"\n".join(f"- {getattr(v,'display_label',v)}" for v in items),encoding="utf-8");return ExportResult(True,str(p))
  except (OSError,ValueError) as exc:return ExportResult(False,error=str(exc))
 def csv(self,path,columns,rows):
  try:
   p=self._path(path);p.parent.mkdir(parents=True,exist_ok=True)
   with p.open("w",newline="",encoding="utf-8") as f:w=csv.writer(f);w.writerow(columns);w.writerows(rows)
   return ExportResult(True,str(p))
  except (OSError,ValueError) as exc:return ExportResult(False,error=str(exc))
