"""Immutable APK Laboratory records."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from enum import Enum
def now():return datetime.now(timezone.utc).isoformat()
class ApkArtifactType(str,Enum):BASE="base-apk";SPLIT="split-apk";SET="apk-set";IMPORTED="imported-apk";DECODED="decoded-directory";DECOMPILED="decompiled-directory";MODIFIED="modified-directory";REBUILT="rebuilt-apk";ALIGNED="aligned-apk";SIGNED="signed-apk"
class ApkDifferenceType(str,Enum):ADDED="added";REMOVED="removed";MODIFIED="modified";UNCHANGED="unchanged"
@dataclass(frozen=True,slots=True)
class ApkArtifact:
 artifact_type:ApkArtifactType;source_path:str;workspace_relative_path:str;sha256:str;file_size:int=0;package_identifier:str="";version_name:str="";version_code:str="";parent_artifact_id:str|None=None;device_serial:str="";target_identifier:str="";trust_classification:str="user-selected";artifact_id:str=field(default_factory=lambda:str(uuid.uuid4()));created_at:str=field(default_factory=now)
 def __post_init__(self):object.__setattr__(self,"artifact_type",ApkArtifactType(self.artifact_type))
 @property
 def display_label(self):return f"{self.artifact_type.value} · {self.package_identifier or 'unknown'} · {self.workspace_relative_path} · {self.sha256 or 'unhashed'}"
 def to_dict(self):d=asdict(self);d["artifact_type"]=self.artifact_type.value;return d
@dataclass(frozen=True,slots=True)
class ApkSetRecord:
 package_identifier:str;base_apk:ApkArtifact|None=None;split_apks:tuple[ApkArtifact,...]=();architecture_splits:tuple[str,...]=();language_splits:tuple[str,...]=();density_splits:tuple[str,...]=();unknown_splits:tuple[str,...]=();complete:bool=False;device_serial:str=""
 @property
 def display_label(self):return f"{self.package_identifier} · base={'yes' if self.base_apk else 'no'} · {len(self.split_apks)} splits · {'complete' if self.complete else 'incomplete'}"
 def to_dict(self):return {**asdict(self),"base_apk":self.base_apk.to_dict() if self.base_apk else None,"split_apks":[x.to_dict() for x in self.split_apks]}
@dataclass(frozen=True,slots=True)
class ApkManifestSummary:
 package_identifier:str="";version_name:str="";version_code:str="";min_sdk:str="";target_sdk:str="";compile_sdk:str="";debuggable:bool|None=None;allow_backup:bool|None=None;cleartext_traffic:bool|None=None;network_security_config:str="";requested_permissions:tuple[str,...]=();application_class:str="";activities:tuple[str,...]=();services:tuple[str,...]=();receivers:tuple[str,...]=();providers:tuple[str,...]=();exported_components:tuple[str,...]=();deep_links:tuple[str,...]=();native_libraries:tuple[str,...]=();architectures:tuple[str,...]=()
 @property
 def display_label(self):return f"{self.package_identifier or 'unknown'} · v{self.version_name or '?'} ({self.version_code or '?'}) · SDK {self.min_sdk or '?'}→{self.target_sdk or '?'} · {len(self.requested_permissions)} permissions"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class ApkSigningRecord:
 schemes:tuple[str,...]=();certificate_subjects:tuple[str,...]=();certificate_issuers:tuple[str,...]=();certificate_serials:tuple[str,...]=();sha256_fingerprints:tuple[str,...]=();validity_periods:tuple[str,...]=();verified:bool=False;signer_count:int=0;source_artifact_id:str=""
 @property
 def display_label(self):return f"{'verified' if self.verified else 'unverified'} · schemes {', '.join(self.schemes) or 'unknown'} · {self.signer_count} signer(s)"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class ApkToolRecord:
 display_name:str;executable_path:str="";installed:bool=False;version:str="";diagnostics:str="";configured_path:str=""
 @property
 def display_label(self):return f"{self.display_name} · {'installed' if self.installed else 'missing/unconfigured'} · {self.version or 'version unknown'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class ApkBuildPlan:
 source_artifact_id:str;workspace_directory:str;decode_mode:str="";instrumentation_mode:str="none";gadget_architecture:str="";gadget_source_path:str="";gadget_config:dict=field(default_factory=dict);rebuild_output:str="";alignment_output:str="";signing_configuration:dict=field(default_factory=dict);installation_serial:str="";command_previews:tuple[tuple[str,...],...]=();state_changing:bool=False;caution_text:str="";required_scope_categories:tuple[str,...]=()
 @property
 def display_label(self):return f"{self.source_artifact_id[:8]} · {self.instrumentation_mode} · {'state-changing' if self.state_changing else 'read-only plan'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class ApkDifference:
 relative_path:str;difference_type:ApkDifferenceType;original_digest:str="";modified_digest:str="";original_size:int=0;modified_size:int=0
 def __post_init__(self):object.__setattr__(self,"difference_type",ApkDifferenceType(self.difference_type))
 @property
 def display_label(self):return f"{self.difference_type.value} · {self.relative_path} · {self.original_size}→{self.modified_size} bytes"
 def to_dict(self):d=asdict(self);d["difference_type"]=self.difference_type.value;return d
