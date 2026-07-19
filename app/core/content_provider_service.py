"""Explicit, bounded, read-only Android content-provider queries."""
from __future__ import annotations
import re
from dataclasses import dataclass
from app.core.storage_models import ContentProviderRecord,ContentQuerySpec
from app.core.pentest_event import EventCategory,PentestEvent

@dataclass(frozen=True,slots=True)
class ProviderResult:
 ok:bool;value:object=None;error:str|None=None;preview:tuple[str,...]=()

class ContentProviderService:
 def __init__(self,adb,component_service,session_provider=lambda:None,timeline_provider=lambda:None,evidence_provider=lambda:None,max_rows=500):self.adb=adb;self.components=component_service;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.max_rows=max_rows
 def list(self,serial,package):
  r=self.components.discover(serial,package)
  if not r.ok:return ProviderResult(False,error=r.error)
  items=[]
  for c in r.value:
   if c.component_type.value=="provider":
    for authority in c.authorities or ("",):items.append(ContentProviderRecord(package,c.name,authority,c.exported,c.enabled,c.permission,c.permission,False,serial))
  return ProviderResult(True,tuple(items))
 def build(self,serial,spec):
  if not serial:return ProviderResult(False,error="An explicitly selected device is required.")
  if not re.match(r"^content://[^\s/]+(?:/.*)?$",spec.content_uri):return ProviderResult(False,error="Enter a valid content:// URI.")
  limit=min(max(1,int(spec.row_limit)),self.max_rows);args=["shell","content","query","--uri",spec.content_uri]
  if spec.projection:args.extend(("--projection",":".join(spec.projection)))
  if spec.selection:args.extend(("--where",spec.selection))
  for value in spec.selection_arguments:args.extend(("--bind",value))
  if spec.sort_order:args.extend(("--sort",spec.sort_order))
  args.extend(("--limit",str(limit)));return ProviderResult(True,tuple(args),preview=(self.adb.adb_path or "adb","-s",serial,*args))
 def query(self,serial,package,spec,confirmed=False,sensitive=False):
  built=self.build(serial,spec)
  if not built.ok:return built
  session=self.session_provider();category="sensitive-data-inspection" if sensitive else "storage-inspection"
  if not session or not (session.permits(category) or (category=="storage-inspection" and session.permits("runtime-inspection"))):return ProviderResult(False,error=f"Active scope does not permit {category}.",preview=built.preview)
  if session.scope.device_serial!=serial or session.scope.package_identifier!=package:return ProviderResult(False,error="Selected device/package does not match active scope.",preview=built.preview)
  if not confirmed:return ProviderResult(False,error="Explicit query confirmation is required.",preview=built.preview)
  r=self.adb.run(*built.value,serial=serial,timeout=30)
  if not r.ok:return ProviderResult(False,error=r.output,preview=built.preview)
  rows=tuple(self.parse(r.stdout)[:min(spec.row_limit,self.max_rows)]);timeline=self.timeline_provider()
  if timeline:timeline.append(PentestEvent(EventCategory.STORAGE,"storage-explorer","Content provider queried",spec.content_uri,related_target_identifier=package))
  return ProviderResult(True,rows,preview=built.preview)
 @staticmethod
 def parse(text):
  rows=[]
  for line in text.splitlines():
   if line.strip().startswith("Row:"):
    body=line.split(" ",2)[-1];row={}
    for part in re.split(r",\s*(?=[^,=]+=)",body):
     if "=" in part:k,v=part.split("=",1);row[k.strip()]=v
    rows.append(row)
  return rows
