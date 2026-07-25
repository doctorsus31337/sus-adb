"""Immutable models for authorized Android network analysis."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from enum import Enum
from typing import Any,Mapping

def now():return datetime.now(timezone.utc).isoformat()
class ProxyMode(str,Enum):NONE="none";GLOBAL_HTTP="global-http";REVERSE="reverse";FORWARDING="forwarding";CUSTOM="custom"
class MappingDirection(str,Enum):FORWARD="forward";REVERSE="reverse"
class CaptureState(str,Enum):IDLE="idle";VALIDATING="validating";STARTING="starting";CAPTURING="capturing";STOPPING="stopping";PULLING="pulling";HASHING="hashing";COMPLETED="completed";FAILED="failed";CANCELLED="cancelled"
class NetworkEventType(str,Enum):CONNECTION="connection";DNS="dns";REQUEST="request";RESPONSE="response";TLS="tls";WEBSOCKET="websocket";SOCKET="socket";PROXY="proxy";CAPTURE="capture";WARNING="warning";ERROR="error";LIFECYCLE="lifecycle"

@dataclass(frozen=True,slots=True)
class HostProxyTool:
 tool_name:str;executable_path:str="";installed:bool=False;version:str="";listening:bool=False;expected_host:str="127.0.0.1";expected_port:int=0;diagnostics:str=""
 @property
 def display_label(self):return f"{self.tool_name} · {'Installed' if self.installed else 'Missing/Unconfigured'} · {'Listening' if self.listening else 'Not confirmed'} · {self.version or 'version unknown'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class DeviceProxyState:
 device_serial:str;proxy_mode:ProxyMode=ProxyMode.NONE;configured_host:str="";configured_port:int=0;original_proxy_value:str="";active_proxy_value:str="";applied_at:str|None=None;restoration_state:str="not-required"
 def __post_init__(self):object.__setattr__(self,"proxy_mode",ProxyMode(self.proxy_mode))
 @property
 def display_label(self):return f"{self.device_serial} · {self.proxy_mode.value} · {self.active_proxy_value or 'none'} · restoration {self.restoration_state}"
 def to_dict(self):d=asdict(self);d["proxy_mode"]=self.proxy_mode.value;return d
@dataclass(frozen=True,slots=True)
class PortMapping:
 device_serial:str;direction:MappingDirection;local_endpoint:str;remote_endpoint:str;active:bool=True;created_at:str=field(default_factory=now);restoration_command_preview:str=""
 def __post_init__(self):object.__setattr__(self,"direction",MappingDirection(self.direction))
 @property
 def display_label(self):return f"{self.direction.value} · {self.local_endpoint} → {self.remote_endpoint} · {'active' if self.active else 'restored'}"
 def to_dict(self):d=asdict(self);d["direction"]=self.direction.value;return d
@dataclass(frozen=True,slots=True)
class PacketCaptureConfig:
 device_serial:str;target_identifier:str="";interface:str="any";capture_filter:str="";snap_length:int=262144;duration:int=30;maximum_file_size:int=50_000_000;remote_path:str="";local_destination:str="";root_required:bool=True
 @property
 def display_label(self):return f"{self.device_serial} · {self.interface} · {self.duration}s · max {self.maximum_file_size} bytes → {self.local_destination}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class PacketCaptureArtifact:
 device_serial:str;target_identifier:str="";remote_path:str="";local_path:str="";start_timestamp:str=field(default_factory=now);stop_timestamp:str|None=None;duration:float=0;file_size:int=0;sha256:str="";packet_count:int|None=None;capture_state:CaptureState=CaptureState.IDLE;evidence_id:str|None=None
 def __post_init__(self):object.__setattr__(self,"capture_state",CaptureState(self.capture_state))
 @property
 def display_label(self):return f"{self.capture_state.value} · {self.local_path or self.remote_path} · {self.file_size} bytes · {self.sha256 or 'unhashed'}"
 def to_dict(self):d=asdict(self);d["capture_state"]=self.capture_state.value;return d
@dataclass(frozen=True,slots=True)
class NetworkEvent:
 event_type:NetworkEventType;source:str="";script_id:str|None=None;process_id:int|None=None;thread_id:str|int|None=None;protocol:str="";direction:str="";host:str="";port:int|None=None;method:str="";url:str="";status_code:int|None=None;headers:Mapping[str,Any]=field(default_factory=dict);body_preview:str="";body_size:int=0;binary_summary:str="";device_serial:str="";target_identifier:str="";severity:str="info";payload:Mapping[str,Any]=field(default_factory=dict);event_id:str=field(default_factory=lambda:str(uuid.uuid4()));timestamp:str=field(default_factory=now)
 def __post_init__(self):object.__setattr__(self,"event_type",NetworkEventType(self.event_type));object.__setattr__(self,"headers",dict(self.headers));object.__setattr__(self,"payload",dict(self.payload))
 @property
 def display_text(self):return f"[{self.timestamp}] {self.event_type.value.upper()} {self.method} {self.url or self.host}{':'+str(self.port) if self.port else ''} {self.status_code or ''}".replace("  "," ").rstrip()
 def to_dict(self):d=asdict(self);d["event_type"]=self.event_type.value;d["display_text"]=self.display_text;return d
