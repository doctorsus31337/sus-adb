"""Immutable device/environment change record."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from enum import Enum
from app.core.assessment_scope import now
class ChangeState(str,Enum): PLANNED="planned"; APPLIED="applied"; RESTORED="restored"; RESTORATION_FAILED="restoration-failed"; ABANDONED="abandoned"
@dataclass(frozen=True,slots=True)
class EnvironmentChange:
    category:str;title:str;description:str="";device_serial:str="";target_identifier:str="";applied_at:str|None=None;restoration_instructions:str="";restoration_command_preview:str="";state:ChangeState=ChangeState.PLANNED;reversible:bool=True;destructive:bool=False;requires_backup:bool=False;backup_evidence_id:str|None=None;notes:str="";related_event_ids:tuple[str,...]=();change_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    def __post_init__(self):object.__setattr__(self,"state",ChangeState(self.state));object.__setattr__(self,"related_event_ids",tuple(self.related_event_ids))
    def to_dict(self):data=asdict(self);data["state"]=self.state.value;return data
    @classmethod
    def from_dict(cls,data):return cls(**data)
