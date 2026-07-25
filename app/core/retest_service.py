"""Retest persistence and audited finding lifecycle updates."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from app.core.finding_validator import FindingValidator
from app.core.retest_record import RetestOutcome
from app.core.security_finding import FindingStatus
@dataclass(frozen=True,slots=True)
class RetestResult:
    ok:bool;record:object|None=None;finding:object|None=None;error:str|None=None
class RetestService:
    STATUS={RetestOutcome.FIXED:FindingStatus.CLOSED,RetestOutcome.PARTIALLY_FIXED:FindingStatus.RETEST_REQUIRED,RetestOutcome.NOT_FIXED:FindingStatus.OPEN,RetestOutcome.UNABLE:FindingStatus.RETEST_REQUIRED,RetestOutcome.REGRESSION:FindingStatus.OPEN}
    def __init__(self,repository,timeline=None):self.repository=repository;self.timeline=timeline;self.path=repository.directory/"retests.jsonl"
    def create(self,record):
        finding=self.repository.get(record.finding_id)
        if not finding:return RetestResult(False,error="Finding was not found.")
        status=self.STATUS[record.outcome];validation=FindingValidator().transition(finding.status,status)
        if not validation.valid:return RetestResult(False,error="; ".join(validation.errors))
        record=record if record.resulting_finding_status==status.value else record.__class__.from_dict({**record.to_dict(),"resulting_finding_status":status.value})
        updated=finding.updated(status=status,evidence_ids=tuple(dict.fromkeys(finding.evidence_ids+record.evidence_ids)))
        result=self.repository.update(updated,finding.status.value)
        if not result.ok:return RetestResult(False,error=result.error)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open("a",encoding="utf-8") as f:f.write(json.dumps(record.to_dict(),sort_keys=True)+"\n")
        return RetestResult(True,record,updated)
    def list(self,finding_id=None):
        if not self.path.exists():return ()
        from app.core.retest_record import RetestRecord
        records=tuple(RetestRecord.from_dict(json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip());return tuple(r for r in records if not finding_id or r.finding_id==finding_id)
    def export_summary(self,path):
        p=self.repository._safe(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps([r.to_dict() for r in self.list()],indent=2,sort_keys=True),encoding="utf-8");return str(p)
