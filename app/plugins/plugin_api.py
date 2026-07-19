"""Capability-gated Plugin API v1 façades; no raw GUI/service exposure."""
from __future__ import annotations
import json,platform
from dataclasses import dataclass
from pathlib import Path
from app.plugins.plugin_capabilities import CapabilityPolicy
PLUGIN_API_VERSION="1.0"
@dataclass(frozen=True,slots=True)
class PluginResult:
    ok:bool;value:object=None;error:str|None=None
@dataclass(frozen=True,slots=True)
class PluginContext:
    application_version:str;platform_name:str;selected_device:dict;selected_target:dict;assessment_scope:dict;session_state:str;theme_tokens:dict;approved_capabilities:tuple[str,...]
class PluginAPI:
    def __init__(self,plugin_id,approved=(),session_provider=lambda:None,device_provider=lambda:None,target_provider=lambda:None,timeline_provider=lambda:None,evidence_provider=lambda:None,finding_provider=lambda:None,state_root="plugins/state",adb_readonly=None,message_sink=None):
        self.plugin_id=plugin_id;self.policy=CapabilityPolicy(approved);self.session_provider=session_provider;self.device_provider=device_provider;self.target_provider=target_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.finding_provider=finding_provider;self.state_root=Path(state_root).resolve();self.adb_readonly=adb_readonly;self.message_sink=message_sink or (lambda *_:None)
    def context(self,app_version="1.0.0",theme=None):
        s=self.session_provider();d=self.device_provider();t=self.target_provider();return PluginContext(app_version,platform.system().lower(),{"serial":getattr(d,"serial","")},{"identifier":getattr(t,"identifier","")},s.scope.to_dict() if s else {},getattr(getattr(s,"state",None),"value","none"),dict(theme or {}),tuple(sorted(self.policy.approved)))
    def _allow(self,capability):
        result=self.policy.check(capability,self.session_provider());return None if result.allowed else PluginResult(False,error=result.error)
    def run_adb_readonly(self,argv):
        denied=self._allow("run-adb-readonly")
        if denied:return denied
        allowed={"getprop","dumpsys","pm","settings","content","ls","stat","sha256sum"}
        if not argv or str(argv[0]) not in allowed:return PluginResult(False,error="Plugin ADB façade permits only documented read-only commands.")
        return PluginResult(True,self.adb_readonly(tuple(argv)) if self.adb_readonly else None)
    def append_timeline(self,event):
        denied=self._allow("append-timeline")
        if denied:return denied
        timeline=self.timeline_provider();return PluginResult(False,error="No active timeline.") if not timeline else PluginResult(timeline.append(event).ok)
    def create_evidence(self,title,text):
        denied=self._allow("create-evidence")
        if denied:return denied
        store=self.evidence_provider();result=store.add_text(title,text,source_tool=f"plugin:{self.plugin_id}") if store else None;return PluginResult(bool(result and result.ok),getattr(result,"item",None),getattr(result,"error","No evidence store."))
    def create_finding(self,finding):
        denied=self._allow("create-findings")
        if denied:return denied
        repo=self.finding_provider();result=repo.create(finding) if repo else None;return PluginResult(bool(result and result.ok),getattr(result,"finding",None),getattr(result,"error","No finding repository."))
    def read_state(self):
        denied=self._allow("read-local-plugin-files")
        if denied:return denied
        p=self.state_root/f"{self.plugin_id}-data.json"
        try:return PluginResult(True,json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})
        except (OSError,ValueError) as exc:return PluginResult(False,error=str(exc))
    def write_state(self,value):
        denied=self._allow("write-plugin-state")
        if denied:return denied
        try:p=self.state_root/f"{self.plugin_id}-data.json";p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2,sort_keys=True),encoding="utf-8");return PluginResult(True)
        except (OSError,TypeError) as exc:return PluginResult(False,error=str(exc))
    def message(self,text,severity="info"):self.message_sink(self.plugin_id,str(text),severity);return PluginResult(True)
