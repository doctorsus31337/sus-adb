"""Immutable, portable security-finding records."""
from __future__ import annotations
import hashlib,json,uuid
from dataclasses import asdict,dataclass,field,replace
from enum import Enum
from typing import Any,Mapping
from app.core.assessment_scope import now

class Severity(str,Enum): INFORMATIONAL="informational";LOW="low";MEDIUM="medium";HIGH="high";CRITICAL="critical"
class Confidence(str,Enum): TENTATIVE="tentative";FIRM="firm";CONFIRMED="confirmed"
class FindingStatus(str,Enum): DRAFT="draft";OPEN="open";NEEDS_REVIEW="needs-review";ACCEPTED_RISK="accepted-risk";REMEDIATED="remediated";RETEST_REQUIRED="retest-required";CLOSED="closed"

@dataclass(frozen=True,slots=True)
class SecurityFinding:
    title:str;summary:str="";detailed_description:str="";severity:Severity=Severity.INFORMATIONAL;confidence:Confidence=Confidence.TENTATIVE;status:FindingStatus=FindingStatus.DRAFT
    affected_device_serials:tuple[str,...]=();affected_target_identifiers:tuple[str,...]=();affected_versions:tuple[str,...]=();component_location:str="";category:str="";weakness_identifiers:tuple[str,...]=();testing_standard_references:tuple[str,...]=();attack_preconditions:str="";impact:str="";likelihood:str="";reproduction_steps:tuple[str,...]=();observed_result:str="";expected_secure_result:str="";remediation:str="";remediation_references:tuple[str,...]=();evidence_ids:tuple[str,...]=();timeline_event_ids:tuple[str,...]=();related_note_ids:tuple[str,...]=();related_script_profile_ids:tuple[str,...]=();discovered_timestamp:str=field(default_factory=now);modified_timestamp:str=field(default_factory=now);tester:str="";reviewer:str="";tags:tuple[str,...]=();sensitivity:str="internal";redaction_state:str="unreviewed";finding_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    def __post_init__(self):
        object.__setattr__(self,"severity",Severity(self.severity));object.__setattr__(self,"confidence",Confidence(self.confidence));object.__setattr__(self,"status",FindingStatus(self.status))
        for name in ("affected_device_serials","affected_target_identifiers","affected_versions","weakness_identifiers","testing_standard_references","reproduction_steps","remediation_references","evidence_ids","timeline_event_ids","related_note_ids","related_script_profile_ids","tags"):object.__setattr__(self,name,tuple(getattr(self,name)))
    @property
    def display_label(self):return f"{self.severity.value.upper()} · {self.title or 'Untitled finding'} · {self.status.value}"
    def to_dict(self):
        data=asdict(self);data.update(severity=self.severity.value,confidence=self.confidence.value,status=self.status.value);return data
    @classmethod
    def from_dict(cls,data:Mapping[str,Any]):return cls(**{k:v for k,v in data.items() if k in cls.__dataclass_fields__})
    @property
    def digest(self):return hashlib.sha256(json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    def updated(self,**changes):return replace(self,modified_timestamp=now(),**changes)
