"""Safe persisted note collection and Markdown export."""
from __future__ import annotations
import json
from dataclasses import dataclass,replace
from pathlib import Path
from app.core.assessment_note import AssessmentNote
from app.core.assessment_scope import now
@dataclass(frozen=True,slots=True)
class NotesResult:
    ok:bool;note:AssessmentNote|None=None;notes:tuple[AssessmentNote,...]=();path:str|None=None;error:str|None=None
class AssessmentNotes:
    def __init__(self,case_root):self.root=Path(case_root).resolve();self.path=self.root/"notes"/"notes.json";self._notes=[]
    def _safe(self,p):
        p=Path(p).resolve();
        if self.root not in p.parents:raise ValueError("Path escapes the case workspace.")
        return p
    def _save(self):self.path.parent.mkdir(parents=True,exist_ok=True);self._safe(self.path).write_text(json.dumps([n.to_dict() for n in self._notes],indent=2,sort_keys=True),encoding="utf-8")
    def load(self):
        try:self._notes=[AssessmentNote.from_dict(v) for v in json.loads(self.path.read_text(encoding="utf-8"))] if self.path.exists() else [];return NotesResult(True,notes=tuple(self._notes))
        except (OSError,ValueError,TypeError) as exc:return NotesResult(False,error=str(exc))
    def create(self,title,body,**kwargs):
        if not title.strip():return NotesResult(False,error="A note title is required.")
        note=AssessmentNote(title.strip(),body,**kwargs);self._notes.append(note);self._save();return NotesResult(True,note)
    def edit(self,note_id,**changes):
        note=next((n for n in self._notes if n.note_id==note_id),None)
        if not note:return NotesResult(False,error="Note was not found.")
        updated=replace(note,modified_at=now(),**changes);self._notes=[updated if n.note_id==note_id else n for n in self._notes];self._save();return NotesResult(True,updated)
    def delete(self,note_id,confirmed=False):
        if not confirmed:return NotesResult(False,error="Explicit deletion confirmation is required.")
        self._notes=[n for n in self._notes if n.note_id!=note_id];self._save();return NotesResult(True)
    def search(self,query="",tag="",priority="All"):
        q=query.casefold();return tuple(n for n in self._notes if (priority=="All" or n.priority==priority) and (not tag or tag in n.tags) and (not q or q in (n.title+n.body+" ".join(n.tags)).casefold()))
    def export_markdown(self,path):
        try:p=self._safe(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text("# Assessment Notes\n\n"+"\n\n".join(f"## {n.title}\n\n{n.body}\n\nTags: {', '.join(n.tags)}" for n in self._notes),encoding="utf-8");return NotesResult(True,path=str(p))
        except (OSError,ValueError) as exc:return NotesResult(False,error=str(exc))
