"""Immutable finding retest record."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from enum import Enum
from app.core.assessment_scope import now
class RetestOutcome(str,Enum): FIXED="fixed";PARTIALLY_FIXED="partially-fixed";NOT_FIXED="not-fixed";UNABLE="unable-to-test";REGRESSION="regression"
@dataclass(frozen=True,slots=True)
class RetestRecord:
    finding_id:str;tested_version:str;tested_device:str;tester:str;outcome:RetestOutcome;notes:str="";evidence_ids:tuple[str,...]=();timeline_event_ids:tuple[str,...]=();resulting_finding_status:str="retest-required";timestamp:str=field(default_factory=now);retest_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    def __post_init__(self):object.__setattr__(self,"outcome",RetestOutcome(self.outcome));object.__setattr__(self,"evidence_ids",tuple(self.evidence_ids));object.__setattr__(self,"timeline_event_ids",tuple(self.timeline_event_ids))
    @property
    def display_label(self):return f"{self.outcome.value} · {self.tested_version or 'version unknown'} · {self.timestamp}"
    def to_dict(self):data=asdict(self);data["outcome"]=self.outcome.value;return data
    @classmethod
    def from_dict(cls,data):return cls(**data)
