"""Digest-bound, local-only plugin trust records."""
from __future__ import annotations
import json
from dataclasses import asdict,dataclass,field
from pathlib import Path
from app.core.assessment_scope import now
@dataclass(frozen=True,slots=True)
class TrustRecord:
    plugin_id:str;package_digest:str;trust_decision:str="untrusted";approved_capabilities:tuple[str,...]=();signer_reference:str="";approval_timestamp:str=field(default_factory=now);operator_note:str="";revoked:bool=False
    def __post_init__(self):object.__setattr__(self,"approved_capabilities",tuple(self.approved_capabilities))
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):return cls(**data)
class PluginTrustStore:
    def __init__(self,path):self.path=Path(path).resolve();self.records={};self.load()
    def load(self):
        try:self.records={k:TrustRecord.from_dict(v) for k,v in json.loads(self.path.read_text(encoding="utf-8")).items()} if self.path.exists() else {}
        except (OSError,ValueError,TypeError):self.records={}
    def _save(self):self.path.parent.mkdir(parents=True,exist_ok=True);self.path.write_text(json.dumps({k:v.to_dict() for k,v in sorted(self.records.items())},indent=2,sort_keys=True),encoding="utf-8")
    def approve(self,plugin_id,digest,capabilities=(),note="",signer_reference="operator-local-review"):
        record=TrustRecord(plugin_id,digest,"trusted-local",tuple(capabilities),signer_reference,operator_note=note);self.records[plugin_id]=record;self._save();return record
    def revoke(self,plugin_id,note=""):
        old=self.records.get(plugin_id)
        if old:self.records[plugin_id]=TrustRecord(old.plugin_id,old.package_digest,"untrusted",(),old.signer_reference,operator_note=note,revoked=True);self._save()
        return self.records.get(plugin_id)
    def verify(self,plugin_id,digest):
        record=self.records.get(plugin_id);return bool(record and not record.revoked and record.trust_decision in {"trusted-local","built-in"} and record.package_digest==digest)
    def approved(self,plugin_id,digest):
        return self.records[plugin_id].approved_capabilities if self.verify(plugin_id,digest) else ()
