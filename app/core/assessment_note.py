"""Immutable assessment note suitable for later finding promotion."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from app.core.assessment_scope import now
@dataclass(frozen=True,slots=True)
class AssessmentNote:
    title:str;body:str;tags:tuple[str,...]=();priority:str="normal";created_at:str=field(default_factory=now);modified_at:str=field(default_factory=now);device_serial:str="";target_identifier:str="";related_evidence_ids:tuple[str,...]=();related_event_ids:tuple[str,...]=();note_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    def __post_init__(self):object.__setattr__(self,"tags",tuple(self.tags));object.__setattr__(self,"related_evidence_ids",tuple(self.related_evidence_ids));object.__setattr__(self,"related_event_ids",tuple(self.related_event_ids))
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):return cls(**data)
