"""Non-mutating Android SharedPreferences XML inspection."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
from app.core.storage_models import SharedPreferenceEntry

@dataclass(frozen=True,slots=True)
class PreferenceResult:
 ok:bool;entries:tuple[SharedPreferenceEntry,...]=();path:str|None=None;error:str|None=None;warning:str|None=None

class SharedPreferencesService:
 def __init__(self,max_preview=160):self.max_preview=max_preview;self.entries=()
 def parse(self,path,device_serial="",target_identifier="",sensitive_keys=()):
  p=Path(path).expanduser().resolve()
  try:
   raw=p.read_text(encoding="utf-8")
   if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():return PreferenceResult(False,error="External entities and DTDs are not permitted.")
   root=ET.fromstring(raw)
   if root.tag!="map":return PreferenceResult(False,error="SharedPreferences root must be <map>.")
   values=[]
   for node in root:
    key=node.attrib.get("name","");kind=node.tag
    if kind=="string":value=node.text or ""
    elif kind in ("int","long"):value=int(node.attrib.get("value","0"))
    elif kind=="float":value=float(node.attrib.get("value","0"))
    elif kind=="boolean":value=node.attrib.get("value","false").casefold()=="true"
    elif kind=="set":value=tuple((child.text or "") for child in node if child.tag=="string")
    elif kind=="null":value=None
    else:value=node.attrib.get("value",node.text)
    shown=json.dumps(value,ensure_ascii=False,default=str) if not isinstance(value,str) else value;preview=shown[:self.max_preview]+("…" if len(shown)>self.max_preview else "");label="likely-sensitive" if key.casefold() in {k.casefold() for k in sensitive_keys} else "unclassified"
    values.append(SharedPreferenceEntry(str(p),key,kind,preview,value,p.stem,device_serial,target_identifier,label))
   self.entries=tuple(values);return PreferenceResult(True,self.entries,str(p))
  except (OSError,ET.ParseError,ValueError,TypeError) as exc:return PreferenceResult(False,error=f"Could not parse SharedPreferences XML: {exc}")
 def search(self,query="",value_type="All"):
  q=query.casefold();return tuple(e for e in self.entries if (value_type=="All" or e.value_type==value_type) and (not q or q in (e.key+e.value_preview+e.namespace).casefold()))
 def reveal(self,entry,session=None):
  if not session or not session.permits("sensitive-data-inspection"):return PreferenceResult(False,error="Sensitive-data-inspection scope is required for full values.")
  return PreferenceResult(True,(entry,))
 def export_json(self,path,entries=None):return self._export(path,json.dumps([e.to_dict() for e in (entries or self.entries)],indent=2,sort_keys=True,ensure_ascii=False,default=str))
 def export_markdown(self,path,entries=None):return self._export(path,"# SharedPreferences\n\n"+"\n".join(f"- `{e.key}` ({e.value_type}): `{e.value_preview}`" for e in (entries or self.entries)))
 @staticmethod
 def compare(first,second):
  a={e.key:e.full_value for e in first};b={e.key:e.full_value for e in second};return {k:{"old":a.get(k),"new":b.get(k)} for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)}
 @staticmethod
 def _export(path,text):
  p=Path(path).expanduser().resolve()
  if p.exists():return PreferenceResult(False,error="Destination exists; overwrite was not authorized.")
  try:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding="utf-8");return PreferenceResult(True,path=str(p))
  except OSError as exc:return PreferenceResult(False,error=str(exc))
