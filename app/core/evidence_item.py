"""Immutable evidence metadata; evidence contents are never executed."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from enum import Enum
from app.core.assessment_scope import now
class EvidenceType(str,Enum):
    SCREENSHOT="screenshot"; SCREEN_RECORDING="screen-recording"; LOG="log"; COMMAND_OUTPUT="command-output"; SCRIPT_EVENT="script-event"; FILE="file"; DATABASE="database"; APK="apk"; REPORT="report"; NOTE="note"; PACKET_CAPTURE="packet-capture"; NETWORK_EVENT="network-event"; MEMORY_OBSERVATION="memory-observation"; RUNTIME_OBSERVATION="runtime-observation"; OTHER="other"
class Sensitivity(str,Enum): PUBLIC="public"; INTERNAL="internal"; CONFIDENTIAL="confidential"; SENSITIVE_TEST_DATA="sensitive-test-data"; POTENTIAL_SECRET="potential-secret"; RESTRICTED="restricted"
@dataclass(frozen=True,slots=True)
class EvidenceItem:
    evidence_type: EvidenceType; title: str; stored_path: str; sha256: str; file_size: int; description: str=""; original_source: str=""; mime_type: str=""; created_at: str=field(default_factory=now); collected_at: str=field(default_factory=now); device_serial: str=""; target_identifier: str=""; related_event_ids: tuple[str,...]=(); tags: tuple[str,...]=(); sensitivity: Sensitivity=Sensitivity.INTERNAL; notes: str=""; derived_from_id: str|None=None; evidence_id: str=field(default_factory=lambda:str(uuid.uuid4()))
    def __post_init__(self): object.__setattr__(self,"evidence_type",EvidenceType(self.evidence_type)); object.__setattr__(self,"sensitivity",Sensitivity(self.sensitivity)); object.__setattr__(self,"related_event_ids",tuple(self.related_event_ids)); object.__setattr__(self,"tags",tuple(self.tags))
    def to_dict(self): data=asdict(self); data["evidence_type"]=self.evidence_type.value; data["sensitivity"]=self.sensitivity.value; return data
    @classmethod
    def from_dict(cls,data): return cls(**data)
