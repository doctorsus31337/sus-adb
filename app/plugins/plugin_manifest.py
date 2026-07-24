"""Immutable, non-executing plugin manifest models."""
from __future__ import annotations
import hashlib,json,re
from dataclasses import asdict,dataclass,field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any,Mapping
from app.core.assessment_scope import now

SEMVER=re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
PLUGIN_ID=re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
CONTRIBUTION_TYPES=("dashboard-card","pentest-panel","menu-action","script-asset","objection-recipe","diagnostic-provider","evidence-processor","finding-template","report-section","report-profile","parser","assessment-action","learning-course")
class TrustState(str,Enum): BUILT_IN="built-in";TRUSTED_LOCAL="trusted-local";UNTRUSTED="untrusted";BLOCKED="blocked"
@dataclass(frozen=True,slots=True)
class ContributionDeclaration:
    contribution_id:str;contribution_type:str;title:str="";factory:str="";metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",dict(self.metadata))
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):return cls(**data)
@dataclass(frozen=True,slots=True)
class PluginManifest:
    plugin_id:str;name:str;version:str;description:str="";author:str="";homepage_source_reference:str="";license:str="";minimum_sus_adb_version:str="0.1.0";supported_platforms:tuple[str,...]=("linux","windows");entry_point:str="plugin.py:Plugin";plugin_api_version:str="1.0";requested_capabilities:tuple[str,...]=();optional_dependencies:tuple[str,...]=();required_external_tools:tuple[str,...]=();contributed_components:tuple[ContributionDeclaration,...]=();addon_ui:Mapping[str,Any]=field(default_factory=dict);trust_state:TrustState=TrustState.UNTRUSTED;enabled:bool=False;package_digest:str="";manifest_digest:str="";installation_timestamp:str=field(default_factory=now);modified_timestamp:str=field(default_factory=now);caution_text:str="Third-party plugins execute as trusted local code only after explicit approval."
    def __post_init__(self):
        if not PLUGIN_ID.fullmatch(self.plugin_id):raise ValueError("Plugin ID must be a stable lowercase identifier.")
        if not SEMVER.fullmatch(self.version):raise ValueError("Plugin version must use semantic versioning.")
        if not SEMVER.fullmatch(self.minimum_sus_adb_version):raise ValueError("Minimum SUS Companion version must use semantic versioning.")
        entry=PurePosixPath(self.entry_point.split(":",1)[0].replace("\\","/"))
        if entry.is_absolute() or ".." in entry.parts:raise ValueError("Entry point must be a portable relative path.")
        object.__setattr__(self,"trust_state",TrustState(self.trust_state));
        for name in ("supported_platforms","requested_capabilities","optional_dependencies","required_external_tools"):object.__setattr__(self,name,tuple(getattr(self,name)))
        object.__setattr__(self,"contributed_components",tuple(v if isinstance(v,ContributionDeclaration) else ContributionDeclaration.from_dict(v) for v in self.contributed_components))
        object.__setattr__(self,"addon_ui",dict(self.addon_ui))
    @property
    def display_label(self):return f"{self.name} {self.version} · {self.trust_state.value} · {'enabled' if self.enabled else 'disabled'}"
    def to_dict(self,include_digest=True):
        data=asdict(self);data["trust_state"]=self.trust_state.value;data["contributed_components"]=[v.to_dict() for v in self.contributed_components]
        if not include_digest:data.pop("manifest_digest",None)
        return data
    def computed_manifest_digest(self):
        data=self.to_dict(False);data.pop("installation_timestamp",None);data.pop("modified_timestamp",None);return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    @classmethod
    def from_dict(cls,data:Mapping[str,Any]):return cls(**{k:v for k,v in data.items() if k in cls.__dataclass_fields__})
