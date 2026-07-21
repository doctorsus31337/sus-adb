"""Authorized, selected-file recovery logic. No operation runs during activation."""
from __future__ import annotations
import hashlib,json
from dataclasses import asdict,dataclass
from pathlib import Path,PurePosixPath
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_ui import PluginPanelSpec,PluginView

PUBLIC_PRESETS=("DCIM","Pictures","Movies","Music","Documents","Download")
DEVICE_STATES=("device","recovery","sideload","bootloader","fastbootd","unauthorized","offline","unavailable")
OUTCOMES=("Ready for authorized recovery","ADB authorization required on device","Device available through public shared storage","Recovery ADB available","Existing root permits selected private-path recovery","Device is encrypted and locked; existing authentication is required","Interactive access or screen replacement is required","MTP/manual recovery may be available","Bootloader unlocking would wipe data and must not be used for recovery","No safe software-only recovery path currently available")

@dataclass(frozen=True,slots=True)
class RecoveryLimits:file_count:int=1000;byte_count:int=2*1024*1024*1024;recursion_depth:int=8;workers:int=2
@dataclass(frozen=True,slots=True)
class RecoveryItem:source:str;destination:str;size:int;source_timestamp:str;recovered_timestamp:str;sha256:str;state:str;error:str=""
@dataclass(frozen=True,slots=True)
class RecoveryResult:ok:bool;items:tuple[RecoveryItem,...]=();error:str|None=None;cancelled:bool=False

def public_paths(base="/sdcard"):
    return tuple(f"{base.rstrip('/')}/{name}" for name in PUBLIC_PRESETS)

def classify_access(state,authorized=False,root=False,encrypted=False,locked=False,mtp=False):
    if state=="unauthorized" or state=="device" and not authorized:return OUTCOMES[1]
    if encrypted and locked:return OUTCOMES[5]
    if state=="recovery" and authorized:return OUTCOMES[3]
    if root and authorized:return OUTCOMES[4]
    if state=="device" and authorized:return OUTCOMES[2]
    if mtp:return OUTCOMES[7]
    if state in {"bootloader","fastbootd"}:return OUTCOMES[8]
    return OUTCOMES[9]

def private_path_allowed(path,root_available,session,confirmed):
    shared=path=="/sdcard" or path.startswith("/sdcard/") or path.startswith("/storage/emulated/")
    if shared:return True
    return bool(root_available and session and session.permits("sensitive-data-inspection") and session.permits("storage-inspection") and confirmed)

class RecoveryEngine:
    """Copies bytes supplied by an injected reader; never invokes ADB itself."""
    def __init__(self,reader,clock=lambda:"1970-01-01T00:00:00+00:00"):self.reader=reader;self.clock=clock
    @staticmethod
    def _relative(value):
        p=PurePosixPath(str(value).replace("\\","/"));clean=PurePosixPath(*[part for part in p.parts if part not in {"/",""}])
        if clean.is_absolute() or ".." in clean.parts:return None
        return clean
    def recover(self,serial,sources,destination,limits=RecoveryLimits(),duplicate="skip",cancelled=lambda:False,resume=()):
        if not serial:return RecoveryResult(False,error="An explicit selected serial is required.")
        if duplicate not in {"skip","rename","replace"}:return RecoveryResult(False,error="Choose skip, rename, or replace explicitly.")
        root=Path(destination).expanduser().resolve()
        if not root.is_dir():return RecoveryResult(False,error="Select an existing writable destination directory.")
        completed={item.source for item in resume if item.state=="recovered"};items=[];count=total=0
        try:
            for selected in sources:
                for record in self.reader(serial,selected,limits.recursion_depth):
                    if cancelled():return RecoveryResult(False,tuple(items),"Recovery cancelled.",True)
                    source,data,stamp=record;relative=self._relative(source.lstrip("/"))
                    if relative is None:return RecoveryResult(False,tuple(items),"Unsafe source path was rejected.")
                    if source in completed:items.append(RecoveryItem(source,"",len(data),stamp,self.clock(),hashlib.sha256(data).hexdigest(),"resumed-skip"));continue
                    count+=1;total+=len(data)
                    if count>limits.file_count or total>limits.byte_count:return RecoveryResult(False,tuple(items),"Configured recovery limits were reached.")
                    target=(root/relative).resolve()
                    if root not in target.parents:return RecoveryResult(False,tuple(items),"Destination escaped the selected boundary.")
                    if target.exists():
                        if duplicate=="skip":items.append(RecoveryItem(source,str(target),len(data),stamp,self.clock(),hashlib.sha256(data).hexdigest(),"skipped"));continue
                        if duplicate=="rename":
                            digest=hashlib.sha256(source.encode()).hexdigest()[:8];target=target.with_name(f"{target.stem}-{digest}{target.suffix}")
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                    items.append(RecoveryItem(source,str(target),len(data),stamp,self.clock(),hashlib.sha256(data).hexdigest(),"recovered"))
            return RecoveryResult(True,tuple(items))
        except (OSError,ValueError) as exc:return RecoveryResult(False,tuple(items),str(exc))

def manifest(items):
    return json.dumps([asdict(item) for item in sorted(items,key=lambda value:(value.source,value.destination))],indent=2,sort_keys=True)+"\n"
def report_section(_context=None):return {"title":"Recovery Results","body":"Operator-selected recovery results only; evidence registration is always explicit."}
def panel_spec(_context=None):
    names=("Overview","Connection","Recovery Plan","Files","Copy Queue","Results","Guidance")
    status={"Selected device":"None","ADB state":"Unavailable","Queued files":"0","Bytes planned":"0","Recovered":"0","Skipped":"0","Failed":"0","Manifest":"Not created"}
    return PluginPanelSpec("Device Rescue & Recovery",tuple(PluginView(name,"No authorized recovery selection is active.",warning="Bootloader unlocking commonly wipes data and must not be used for recovery.") for name in names),status)
class Plugin:
    def activate(self,api):
        self.api=api
        return (Contribution("device-rescue.dashboard","dashboard-card","Device Rescue & Recovery",factory=panel_spec),Contribution("device-rescue.panel","pentest-panel","Device Rescue & Recovery",factory=panel_spec),Contribution("device-rescue.menu","menu-action","Open Device Rescue",metadata={"target":"device-rescue.panel"}),Contribution("device-rescue.report","report-section","Recovery Results",factory=report_section,capability_requirement="contribute-report-section"),Contribution("device-rescue.manifest","evidence-processor","Recovery Manifest Exporter"))
    def deactivate(self):self.api=None
