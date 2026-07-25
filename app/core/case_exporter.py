"""Deterministic, case-local exports containing metadata but no evidence contents."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True,slots=True)
class ExportResult:
    ok:bool;path:str|None=None;error:str|None=None
class CaseExporter:
    def __init__(self,case_root):self.root=Path(case_root).resolve();self.exports=(self.root/"exports").resolve()
    def _safe(self,name):
        p=(self.exports/name).resolve()
        if p!=self.exports and self.exports not in p.parents:raise ValueError("Export path escapes the case exports directory.")
        return p
    def _write(self,name,text):
        try:p=self._safe(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding="utf-8");return ExportResult(True,str(p))
        except (OSError,ValueError) as exc:return ExportResult(False,error=str(exc))
    def summary_data(self,session,evidence=(),events=(),notes=(),changes=()):
        unresolved=[c.to_dict() for c in changes if c.state.value not in {"restored","abandoned"}]
        return {"session":session.to_dict(),"scope_digest":session.scope.digest,"authorization_confirmed":session.scope.authorization_confirmed,"allowed_actions":list(session.scope.allowed_actions),"excluded_actions":list(session.scope.excluded_actions),"tool_snapshot":dict(session.tool_snapshot),"evidence_manifest":[i.to_dict() for i in evidence],"timeline":[e.to_dict() for e in events],"notes":[n.to_dict() for n in notes],"unresolved_environment_changes":unresolved}
    def export_json(self,session,**collections):return self._write("case-summary.json",json.dumps(self.summary_data(session,**collections),indent=2,sort_keys=True,default=str))
    def export_markdown(self,session,evidence=(),events=(),notes=(),changes=()):
        unresolved=[c for c in changes if c.state.value not in {"restored","abandoned"}]
        text=f"# {session.scope.case_name}\n\n**Authorization confirmed:** {session.scope.authorization_confirmed}\n\n**Scope digest:** `{session.scope.digest}`\n\n**State:** {session.state.value}\n\n## Allowed Actions\n"+"\n".join(f"- {v}" for v in session.scope.allowed_actions)+"\n\n## Excluded Actions\n"+"\n".join(f"- {v}" for v in session.scope.excluded_actions)+"\n\n## Evidence Manifest\n"+"\n".join(f"- {i.title}: `{i.sha256}`" for i in evidence)+"\n\n## Unresolved Environment Changes\n"+(("\n".join(f"- **{c.title}** — {c.restoration_instructions}" for c in unresolved)) or "- None")+"\n\n## Tool Snapshot\n```json\n"+json.dumps(dict(session.tool_snapshot),indent=2,sort_keys=True)+"\n```\n"
        return self._write("case-summary.md",text)
    def unresolved_checklist(self,changes):return self._write("unresolved-changes.md","# Unresolved Environment Changes\n\n"+"\n".join(f"- [ ] {c.title}: {c.restoration_instructions}" for c in changes if c.state.value not in {"restored","abandoned"}))
