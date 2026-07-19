"""Append-only safe JSONL assessment timeline."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from app.core.pentest_event import PentestEvent
@dataclass(frozen=True,slots=True)
class TimelineResult:
    ok: bool; events: tuple[PentestEvent,...]=(); path: str|None=None; error: str|None=None; malformed_records: int=0
class SessionTimeline:
    def __init__(self,case_root): self.root=Path(case_root).resolve(); self.path=self.root/"timeline"/"events.jsonl"; self._events=[]
    def _safe(self,path):
        p=(self.root/Path(path)).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        if p!=self.root and self.root not in p.parents: raise ValueError("Path escapes the case workspace.")
        return p
    def append(self,event):
        try:
            path=self._safe(self.path); path.parent.mkdir(parents=True,exist_ok=True)
            with path.open("a",encoding="utf-8") as stream: stream.write(json.dumps(event.to_dict(),sort_keys=True,default=str)+"\n")
            self._events.append(event); return TimelineResult(True,(event,),str(path))
        except (OSError,ValueError,TypeError) as exc: return TimelineResult(False,error=str(exc))
    def rebuild(self):
        valid=[]; malformed=0
        if not self.path.exists(): self._events=[]; return TimelineResult(True)
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try: valid.append(PentestEvent.from_dict(json.loads(line)))
            except (ValueError,TypeError,KeyError,json.JSONDecodeError): malformed+=1
        self._events=sorted(valid,key=lambda e:e.timestamp); return TimelineResult(True,tuple(self._events),str(self.path),malformed_records=malformed)
    def events(self): return tuple(sorted(self._events,key=lambda e:e.timestamp))
    def filter(self,query="",category="All",severity="All",source="All"):
        q=query.casefold().strip()
        return tuple(e for e in self.events() if (category=="All" or e.category.value==category) and (severity=="All" or e.severity==severity) and (source=="All" or e.source==source) and (not q or q in (e.display_text+json.dumps(e.payload,default=str)).casefold()))
    def export_json(self,path,events=None):
        try: p=self._safe(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps([e.to_dict() for e in (events or self.events())],indent=2,sort_keys=True,default=str),encoding="utf-8"); return TimelineResult(True,path=str(p))
        except (OSError,ValueError) as exc:return TimelineResult(False,error=str(exc))
    def export_markdown(self,path,events=None):
        try: p=self._safe(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text("# Assessment Timeline\n\n"+"\n".join(f"- {e.display_text}" for e in (events or self.events())),encoding="utf-8"); return TimelineResult(True,path=str(p))
        except (OSError,ValueError) as exc:return TimelineResult(False,error=str(exc))
    def correction(self,event_id,description,source="operator"): return self.append(PentestEvent.correction(event_id,description,source))
