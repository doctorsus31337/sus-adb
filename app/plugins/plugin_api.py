"""Capability-gated Plugin API v1 façades; no raw GUI/service exposure."""
from __future__ import annotations
import json,platform
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from app.plugins.plugin_capabilities import CapabilityPolicy
PLUGIN_API_VERSION="1.0"
@dataclass(frozen=True,slots=True)
class PluginResult:
    ok:bool;value:object=None;error:str|None=None
@dataclass(frozen=True,slots=True)
class PluginContext:
    application_version:str;platform_name:str;selected_device:object;selected_target:object;assessment_scope:object;session_state:str;theme_tokens:object;approved_capabilities:tuple[str,...]
    devices:tuple[object,...]=();adb_state:str="unavailable";interface_mode:str="advanced";lifecycle:str="ready";generation:int=0;updated_at:str=""
class PluginAPI:
    def __init__(self,plugin_id,approved=(),session_provider=lambda:None,device_provider=lambda:None,target_provider=lambda:None,timeline_provider=lambda:None,evidence_provider=lambda:None,finding_provider=lambda:None,state_root="plugins/state",adb_readonly=None,message_sink=None,host_state=None,app_version="1.0.0"):
        self.plugin_id=plugin_id;self.policy=CapabilityPolicy(approved);self.session_provider=session_provider;self.device_provider=device_provider;self.target_provider=target_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.finding_provider=finding_provider;self.state_root=Path(state_root).resolve();self.adb_readonly=adb_readonly;self.message_sink=message_sink or (lambda *_:None);self.host_state=host_state;self.app_version=app_version;self._subscriptions=[];self._closed=False
    @staticmethod
    def _immutable(value):
        return MappingProxyType(dict(value or {}))
    def context(self,app_version=None,theme=None,snapshot=None):
        if snapshot is None and self.host_state is not None:snapshot=self.host_state.snapshot()
        device_allowed="read-selected-device" in self.policy.approved
        target_allowed="read-selected-target" in self.policy.approved
        scope_allowed="access-active-case" in self.policy.approved
        if snapshot is not None:
            device=snapshot.selected_device.to_dict() if device_allowed and snapshot.selected_device else {}
            target=snapshot.selected_target.to_dict() if target_allowed and snapshot.selected_target else {}
            scope=snapshot.assessment_scope.to_dict() if scope_allowed and snapshot.assessment_scope else {}
            devices=tuple(self._immutable(item.to_dict()) for item in snapshot.devices) if device_allowed else ()
            return PluginContext(app_version or self.app_version,platform.system().lower(),self._immutable(device),self._immutable(target),self._immutable(scope),snapshot.session_state if scope_allowed else "none",self._immutable(theme),tuple(sorted(self.policy.approved)),devices,snapshot.adb_state if device_allowed else "unavailable",snapshot.interface_mode,snapshot.lifecycle,snapshot.generation,snapshot.updated_at)
        s=self.session_provider();d=self.device_provider();t=self.target_provider()
        return PluginContext(app_version or self.app_version,platform.system().lower(),self._immutable({"serial":getattr(d,"serial","")} if device_allowed else {}),self._immutable({"identifier":getattr(t,"identifier","")} if target_allowed else {}),self._immutable(s.scope.to_dict() if scope_allowed and s else {}),getattr(getattr(s,"state",None),"value","none") if scope_allowed else "none",self._immutable(theme),tuple(sorted(self.policy.approved)))
    def subscribe_context(self,callback,*,replay=True):
        if self._closed:return PluginResult(False,error="Plugin API ownership has ended.")
        if self.host_state is None:return PluginResult(False,error="Live host state is unavailable.")
        latest=[-1];active=[True]
        def deliver(snapshot):
            if not active[0] or self._closed or snapshot.generation<=latest[0]:return
            latest[0]=snapshot.generation;callback(self.context(snapshot=snapshot))
        handle=self.host_state.subscribe(f"plugin:{self.plugin_id}",deliver,replay=replay)
        def cancel():
            active[0]=False;handle.cancel()
            if cancellation in self._subscriptions:self._subscriptions.remove(cancellation)
        cancellation=__import__("app.core.host_state",fromlist=["StateSubscription"]).StateSubscription(cancel);self._subscriptions.append(cancellation);return cancellation
    def close(self):
        self._closed=True
        for handle in tuple(self._subscriptions):handle.cancel()
        self._subscriptions.clear()
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
