"""Immutable report profiles and reproducible snapshots."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from typing import Any,Mapping
from app.core.assessment_scope import now
@dataclass(frozen=True,slots=True)
class ReportProfile:
    name:str;organization:str="";report_title:str="Security Assessment Report";report_subtitle:str="";author:str="";reviewer:str="";classification:str="Internal";audience:str="Technical and executive";template:str="gothic";included_sections:tuple[str,...]=("authorization","executive-summary","methodology","tools","timeline","findings","evidence","changes","limitations","remediation","appendix");included_finding_statuses:tuple[str,...]=("open","needs-review","accepted-risk","remediated","retest-required","closed");minimum_finding_severity:str="informational";evidence_inclusion_policy:str="metadata-only";redaction_policy:str="explicit";include_commands:bool=False;include_script_names:bool=True;include_timeline_summary:bool=True;include_environment_changes:bool=True;include_appendix:bool=True;logo_path_reference:str="";created_timestamp:str=field(default_factory=now);modified_timestamp:str=field(default_factory=now);profile_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    def __post_init__(self):object.__setattr__(self,"included_sections",tuple(self.included_sections));object.__setattr__(self,"included_finding_statuses",tuple(self.included_finding_statuses));object.__setattr__(self,"logo_path_reference",self.logo_path_reference.replace("\\","/").lstrip("/"))
    @property
    def display_label(self):return f"{self.name} · {self.classification}"
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data:Mapping[str,Any]):return cls(**{k:v for k,v in data.items() if k in cls.__dataclass_fields__})
@dataclass(frozen=True,slots=True)
class ReportSnapshot:
    case_id:str;scope_digest:str;session_state:str;report_profile:ReportProfile;selected_finding_ids:tuple[str,...]=();finding_digests:tuple[str,...]=();evidence_manifest_digest:str="";timeline_digest:str="";unresolved_change_count:int=0;completeness_warnings:tuple[str,...]=();output_paths:tuple[str,...]=();generated_timestamp:str=field(default_factory=now);snapshot_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    def __post_init__(self):
        if not isinstance(self.report_profile,ReportProfile):object.__setattr__(self,"report_profile",ReportProfile.from_dict(self.report_profile))
        for name in ("selected_finding_ids","finding_digests","completeness_warnings","output_paths"):object.__setattr__(self,name,tuple(getattr(self,name)))
        object.__setattr__(self,"output_paths",tuple(str(p).replace("\\","/").lstrip("/") for p in self.output_paths))
    @property
    def display_label(self):return f"{self.report_profile.name} · {self.generated_timestamp} · {len(self.selected_finding_ids)} findings"
    def to_dict(self):data=asdict(self);data["report_profile"]=self.report_profile.to_dict();return data
    @classmethod
    def from_dict(cls,data):return cls(**data)
