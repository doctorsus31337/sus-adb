"""Immutable structured records used by Advanced ADB Explorer."""
from __future__ import annotations
from dataclasses import asdict,dataclass,field
from enum import Enum
from app.core.assessment_scope import now
class ComponentType(str,Enum): ACTIVITY="activity";SERVICE="service";RECEIVER="receiver";PROVIDER="provider"
class RemoteEntryType(str,Enum): FILE="file";DIRECTORY="directory";SYMLINK="symlink";UNKNOWN="unknown"
class AccessMethod(str,Enum): NORMAL="normal-shell";RUN_AS="run-as";ROOT="root"
class CaptureType(str,Enum): SCREENSHOT="screenshot";SCREEN_RECORDING="screen-recording"
@dataclass(frozen=True,slots=True)
class PackageRecord:
 identifier:str;label:str="";version_name:str="";version_code:str="";uid:str="";enabled:bool|None=None;system:bool=False;debuggable:bool|None=None;data_directory:str="";apk_paths:tuple[str,...]=();installer:str="";requested_permissions:tuple[str,...]=();granted_permissions:tuple[str,...]=();first_install_time:str="";last_update_time:str="";serial:str=""
 @property
 def display_label(self):return f"{self.label+' — ' if self.label else ''}{self.identifier}"
 def to_dict(self):return asdict(self)
 @classmethod
 def from_dict(cls,d):return cls(**d)
@dataclass(frozen=True,slots=True)
class ComponentRecord:
 component_type:ComponentType;package_identifier:str;class_name:str;exported:bool|None=None;enabled:bool|None=None;required_permission:str="";intent_actions:tuple[str,...]=();intent_categories:tuple[str,...]=();authorities:tuple[str,...]=();process_name:str="";serial:str=""
 def __post_init__(self):object.__setattr__(self,"component_type",ComponentType(self.component_type))
 @property
 def component_name(self):return self.class_name if "/" in self.class_name else f"{self.package_identifier}/{self.class_name}"
 @property
 def display_label(self):return f"{self.component_type.value.title()} · {self.component_name}"
 def to_dict(self):d=asdict(self);d["component_type"]=self.component_type.value;return d
 @classmethod
 def from_dict(cls,d):return cls(**d)
@dataclass(frozen=True,slots=True)
class RemoteFileEntry:
 name:str;remote_path:str;entry_type:RemoteEntryType=RemoteEntryType.UNKNOWN;size:int|None=None;mode:str="";owner:str="";group:str="";modified_at:str="";symlink_target:str="";access_method:AccessMethod=AccessMethod.NORMAL;serial:str="";target_identifier:str=""
 def __post_init__(self):object.__setattr__(self,"entry_type",RemoteEntryType(self.entry_type));object.__setattr__(self,"access_method",AccessMethod(self.access_method))
 @property
 def display_label(self):return f"{self.name} — {self.entry_type.value} — {self.size if self.size is not None else '?'} bytes"
 def to_dict(self):d=asdict(self);d["entry_type"]=self.entry_type.value;d["access_method"]=self.access_method.value;return d
 @classmethod
 def from_dict(cls,d):return cls(**d)
@dataclass(frozen=True,slots=True)
class LogcatEvent:
 timestamp:str;pid:int;tid:int;priority:str;tag:str;message:str;raw_line:str;serial:str="";target_identifier:str=""
 @property
 def display_label(self):return f"{self.timestamp} {self.priority}/{self.tag}({self.pid}): {self.message}"
 def to_dict(self):return asdict(self)
 @classmethod
 def from_dict(cls,d):return cls(**d)
@dataclass(frozen=True,slots=True)
class CaptureArtifact:
 capture_type:CaptureType;local_path:str;remote_path:str="";created_at:str=field(default_factory=now);duration:int|None=None;dimensions:str="";sha256:str="";serial:str="";target_identifier:str=""
 def __post_init__(self):object.__setattr__(self,"capture_type",CaptureType(self.capture_type))
 @property
 def display_label(self):return f"{self.capture_type.value} · {self.local_path} · {self.sha256[:12]}"
 def to_dict(self):d=asdict(self);d["capture_type"]=self.capture_type.value;return d
 @classmethod
 def from_dict(cls,d):return cls(**d)
