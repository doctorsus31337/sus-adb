"""Scope-aware, audit-integrated change tracking; never executes commands."""
from __future__ import annotations
import json
from dataclasses import dataclass,replace
from pathlib import Path
from app.core.assessment_scope import AssessmentScope,now
from app.core.environment_change import ChangeState,EnvironmentChange
from app.core.pentest_event import EventCategory,PentestEvent
@dataclass(frozen=True,slots=True)
class ChangeResult:
    ok:bool;change:EnvironmentChange|None=None;changes:tuple[EnvironmentChange,...]=();error:str|None=None
class EnvironmentChangeTracker:
    def __init__(self,case_root,timeline=None):self.root=Path(case_root).resolve();self.path=self.root/"case-changes.json";self.timeline=timeline;self._changes=[]
    def _safe(self,p):
        p=Path(p).resolve();
        if self.root not in p.parents:raise ValueError("Path escapes the case workspace.")
        return p
    def _save(self):self.root.mkdir(parents=True,exist_ok=True);self._safe(self.path).write_text(json.dumps([c.to_dict() for c in self._changes],indent=2,sort_keys=True),encoding="utf-8")
    def load(self):
        try:self._changes=[EnvironmentChange.from_dict(v) for v in json.loads(self.path.read_text(encoding="utf-8"))] if self.path.exists() else [];return ChangeResult(True,changes=tuple(self._changes))
        except (OSError,ValueError,TypeError) as exc:return ChangeResult(False,error=str(exc))
    def register(self,change):self._changes.append(change);self._save();self._event(change,"Planned environment change");return ChangeResult(True,change)
    def mark_applied(self,change_id,scope:AssessmentScope,confirmed=False,session_active=False):
        change=self._find(change_id)
        if not change:return ChangeResult(False,error="Environment change was not found.")
        if not session_active:return ChangeResult(False,error="An active authorized assessment session is required.")
        category="destructive-testing" if change.destructive else "state-changing-testing"
        if not scope.allows(category):return ChangeResult(False,error=f"Active scope does not permit {category}.")
        if (change.destructive or not change.reversible) and not confirmed:return ChangeResult(False,error="Explicit confirmation is required for destructive or irreversible changes.")
        return self._update(change,ChangeState.APPLIED,applied_at=now())
    def mark_restored(self,change_id):return self._state(change_id,ChangeState.RESTORED)
    def mark_restoration_failed(self,change_id,notes=""):return self._state(change_id,ChangeState.RESTORATION_FAILED,notes=notes)
    def abandon(self,change_id,confirmed=False):return self._state(change_id,ChangeState.ABANDONED) if confirmed else ChangeResult(False,error="Explicit abandonment confirmation is required.")
    def _state(self,change_id,state,**changes):
        change=self._find(change_id);return self._update(change,state,**changes) if change else ChangeResult(False,error="Environment change was not found.")
    def _update(self,change,state,**changes):
        updated=replace(change,state=state,**changes);self._changes=[updated if c.change_id==change.change_id else c for c in self._changes];self._save();self._event(updated,f"Environment change {state.value}");return ChangeResult(True,updated)
    def _find(self,cid):return next((c for c in self._changes if c.change_id==cid),None)
    def unresolved(self):return tuple(c for c in self._changes if c.state in {ChangeState.PLANNED,ChangeState.APPLIED,ChangeState.RESTORATION_FAILED})
    def filter(self,query="",category="All",unresolved_only=False):
        q=query.casefold();source=self.unresolved() if unresolved_only else tuple(self._changes);return tuple(c for c in source if (category=="All" or c.category==category) and (not q or q in (c.title+c.description+c.restoration_instructions).casefold()))
    @staticmethod
    def restoration_guidance(change):return f"{change.restoration_instructions}\nCommand preview (guidance only; not executed): {change.restoration_command_preview}".strip()
    def _event(self,change,title):
        if self.timeline:self.timeline.append(PentestEvent(EventCategory.ENVIRONMENT_CHANGE,"change-tracker",title,change.title,payload={"change_id":change.change_id,"state":change.state.value,"restoration_preview":change.restoration_command_preview}))
