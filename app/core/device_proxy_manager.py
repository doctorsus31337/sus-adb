"""Scope-aware selected-device Android proxy and mapping management."""
from __future__ import annotations
from dataclasses import dataclass,replace
from app.core.assessment_scope import now
from app.core.environment_change import EnvironmentChange
from app.core.network_models import DeviceProxyState,MappingDirection,PortMapping,ProxyMode
from app.core.pentest_event import EventCategory,PentestEvent

@dataclass(frozen=True,slots=True)
class ProxyResult:
 ok:bool;value:object=None;error:str|None=None;preview:tuple[str,...]=()

class DeviceProxyManager:
 def __init__(self,adb,session_provider=lambda:None,timeline_provider=lambda:None,change_provider=lambda:None):self.adb=adb;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.change_provider=change_provider;self.serial="";self.state=None;self.mappings=[]
 def select(self,serial):
  if serial!=self.serial:self.serial=serial or "";self.state=None;self.mappings=[]
 def _guard(self,confirmed):
  session=self.session_provider()
  if not self.serial:return "An explicitly selected device is required."
  if not session or not session.permits("network-analysis"):return "An active authorized assessment permitting network-analysis is required."
  if session.scope.device_serial!=self.serial:return "The selected device does not match the active scope."
  if not confirmed:return "Explicit confirmation is required."
  return None
 @staticmethod
 def endpoint(host,port):
  host=str(host).strip()
  try:port=int(port)
  except (TypeError,ValueError):raise ValueError("Proxy port must be an integer.")
  if not host or any(c.isspace() for c in host) or not 1<=port<=65535:raise ValueError("An explicit proxy host and valid port are required.")
  return f"{host}:{port}"
 def inspect(self):
  if not self.serial:return ProxyResult(False,error="An explicitly selected device is required.")
  proxy=self.adb.run("shell","settings","get","global","http_proxy",serial=self.serial,timeout=10)
  forwards=self.adb.run("forward","--list",serial=self.serial,timeout=10);reverses=self.adb.run("reverse","--list",serial=self.serial,timeout=10)
  if not proxy.ok:return ProxyResult(False,error=proxy.output)
  original=proxy.stdout.strip();self.state=self.state or DeviceProxyState(self.serial,original_proxy_value=original,active_proxy_value=original)
  return ProxyResult(True,{"state":self.state,"forward":forwards.stdout,"reverse":reverses.stdout})
 def preview_proxy(self,host,port):
  try:value=self.endpoint(host,port);return ProxyResult(True,preview=("adb","-s",self.serial,"shell","settings","put","global","http_proxy",value))
  except ValueError as exc:return ProxyResult(False,error=str(exc))
 def apply_proxy(self,host,port,confirmed=False):
  error=self._guard(confirmed)
  if error:return ProxyResult(False,error=error)
  if self.state is None:
   inspected=self.inspect()
   if not inspected.ok:return inspected
  try:value=self.endpoint(host,port)
  except ValueError as exc:return ProxyResult(False,error=str(exc))
  result=self.adb.run("shell","settings","put","global","http_proxy",value,serial=self.serial,timeout=10)
  if not result.ok:return ProxyResult(False,error=result.output)
  self.state=replace(self.state,proxy_mode=ProxyMode.GLOBAL_HTTP,configured_host=str(host),configured_port=int(port),active_proxy_value=value,applied_at=now(),restoration_state="required");self._record("Device proxy applied",value,"shell settings put global http_proxy "+self.state.original_proxy_value);return ProxyResult(True,self.state)
 def clear_proxy(self,confirmed=False):return self._set_proxy(":0",ProxyMode.NONE,"Device proxy cleared",confirmed)
 def restore_proxy(self,confirmed=False):
  if self.state is None:return ProxyResult(False,error="Capture the original device proxy state first.")
  value=self.state.original_proxy_value or ":0";result=self._set_proxy(value,ProxyMode.NONE,"Original device proxy restored",confirmed)
  if result.ok:self.state=replace(self.state,restoration_state="restored")
  return result
 def _set_proxy(self,value,mode,title,confirmed):
  error=self._guard(confirmed)
  if error:return ProxyResult(False,error=error)
  result=self.adb.run("shell","settings","put","global","http_proxy",value,serial=self.serial,timeout=10)
  if not result.ok:return ProxyResult(False,error=result.output)
  if self.state:self.state=replace(self.state,proxy_mode=mode,active_proxy_value=value,applied_at=now(),restoration_state="required")
  self._event(title,value);return ProxyResult(True,self.state)
 def add_mapping(self,direction,local,remote,confirmed=False):
  error=self._guard(confirmed)
  if error:return ProxyResult(False,error=error)
  direction=MappingDirection(direction);result=self.adb.run(direction.value,local,remote,serial=self.serial,timeout=10)
  if not result.ok:return ProxyResult(False,error=result.output)
  preview=f"adb -s {self.serial} {direction.value} --remove {local}";mapping=PortMapping(self.serial,direction,local,remote,restoration_command_preview=preview);self.mappings.append(mapping);self._record(f"ADB {direction.value} mapping added",mapping.display_label,preview);return ProxyResult(True,mapping)
 def add_forward(self,local,remote,confirmed=False):return self.add_mapping(MappingDirection.FORWARD,local,remote,confirmed)
 def add_reverse(self,local,remote,confirmed=False):return self.add_mapping(MappingDirection.REVERSE,local,remote,confirmed)
 def remove_mapping(self,mapping,confirmed=False):
  if mapping not in self.mappings:return ProxyResult(False,error="Only SUS-ADB-owned mappings can be removed.")
  error=self._guard(confirmed)
  if error:return ProxyResult(False,error=error)
  result=self.adb.run(mapping.direction.value,"--remove",mapping.local_endpoint,serial=self.serial,timeout=10)
  if not result.ok:return ProxyResult(False,error=result.output)
  self.mappings.remove(mapping);self._event("ADB mapping restored",mapping.display_label);return ProxyResult(True,replace(mapping,active=False))
 def remove_forward(self,mapping,confirmed=False):return self.remove_mapping(mapping,confirmed) if mapping.direction is MappingDirection.FORWARD else ProxyResult(False,error="Select a SUS-ADB-owned forward mapping.")
 def remove_reverse(self,mapping,confirmed=False):return self.remove_mapping(mapping,confirmed) if mapping.direction is MappingDirection.REVERSE else ProxyResult(False,error="Select a SUS-ADB-owned reverse mapping.")
 def restore_all(self,confirmed=False):
  results=[self.remove_mapping(item,confirmed) for item in tuple(self.mappings)]
  if self.state and self.state.restoration_state=="required":results.append(self.restore_proxy(confirmed))
  return tuple(results)
 def owned_changes(self):return tuple(self.mappings)+(tuple((self.state,)) if self.state and self.state.restoration_state=="required" else ())
 def guidance(self):return "Restore only listed SUS-ADB mappings, then restore Android global http_proxy to the captured original value. Certificate trust and TLS pinning are separate states."
 def _record(self,title,description,restore):
  tracker=self.change_provider()
  if tracker:tracker.register(EnvironmentChange("network",title,description,self.serial,restoration_instructions="Run the visible restoration command after authorized testing.",restoration_command_preview=restore))
  self._event(title,description)
 def _event(self,title,description):
  timeline=self.timeline_provider()
  if timeline:timeline.append(PentestEvent(EventCategory.NETWORK,"network-workspace",title,description,related_target_identifier=getattr(self.session_provider().scope,"package_identifier",None) if self.session_provider() else None))
