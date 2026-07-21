"""Read-only bootloader and root-readiness assessment; command previews only."""
from __future__ import annotations
import hashlib,json,zipfile
from dataclasses import asdict,dataclass
from pathlib import Path,PurePosixPath
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_ui import PluginPanelSpec,PluginView

@dataclass(frozen=True,slots=True)
class FirmwareAssessment:path:str;sha256:str;size:int;classification:str;metadata:tuple[tuple[str,str],...];warnings:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class ReadinessMatrix:passed:tuple[str,...];blockers:tuple[str,...];warnings:tuple[str,...];unknowns:tuple[str,...];data_wipe_likely:bool;command_previews:tuple[str,...]=()

PROPERTY_MAP={"manufacturer":"ro.product.manufacturer","model":"ro.product.model","product":"ro.product.name","codename":"ro.product.device","hardware":"ro.hardware","fingerprint":"ro.build.fingerprint","android":"ro.build.version.release","sdk":"ro.build.version.sdk","patch":"ro.build.version.security_patch","architecture":"ro.product.cpu.abi","abis":"ro.product.cpu.abilist","bootloader":"ro.bootloader","baseband":"gsm.version.baseband","verified_boot":"ro.boot.verifiedbootstate","vbmeta":"ro.boot.vbmeta.device_state","slot":"ro.boot.slot_suffix","dynamic_partitions":"ro.boot.dynamic_partitions","virtual_ab":"ro.virtual_ab.enabled","encryption":"ro.crypto.state","system_as_root":"ro.build.system_root_image"}
def parse_properties(text):
    values={}
    for line in text.splitlines():
        if line.startswith("[") and "]: [" in line:
            key,value=line[1:].split("]: [",1);values[key]=value.rstrip("]")
        elif "=" in line:key,value=line.split("=",1);values[key.strip()]=value.strip()
    return {name:values.get(prop,"") for name,prop in PROPERTY_MAP.items()}
def parse_boot_state(props):
    lock=props.get("ro.boot.flash.locked") or ("0" if props.get("vbmeta")=="unlocked" else "")
    return {"locked":True if lock=="1" else False if lock=="0" else None,"oem_unlock_visible":props.get("sys.oem_unlock_allowed","unknown"),"verified_boot":props.get("verified_boot") or "unknown","avb":props.get("ro.boot.avb_version","unknown"),"slot":props.get("slot") or "unknown","dynamic":props.get("dynamic_partitions") or "unknown","root":props.get("root","unknown"),"magisk":props.get("magisk","unknown")}
def inspect_firmware(path,device_codename="",max_bytes=4*1024*1024):
    p=Path(path).resolve();data=p.read_bytes();digest=hashlib.sha256(data).hexdigest();metadata={};warnings=[]
    if zipfile.is_zipfile(p):
        with zipfile.ZipFile(p) as archive:
            infos=archive.infolist()
            if any(PurePosixPath(i.filename).is_absolute() or ".." in PurePosixPath(i.filename).parts for i in infos):raise ValueError("Unsafe archive traversal entry.")
            for info in infos:
                if info.file_size>max_bytes:continue
                if PurePosixPath(info.filename).name in {"android-info.txt","metadata"}:
                    text=archive.read(info).decode("utf-8","replace")[:max_bytes]
                    for line in text.splitlines():
                        if "=" in line:key,value=line.split("=",1);metadata[key.strip()]=value.strip()
    else:
        head=data[:4096]
        if head.startswith(b"ANDROID!"):metadata["image"]="android-boot"
        elif head.startswith(b"AVB0"):metadata["image"]="vbmeta"
        else:warnings.append("Header metadata is insufficient.")
    product=metadata.get("require product",metadata.get("pre-device",""));classification="insufficient metadata"
    if product and device_codename:classification="compatible" if device_codename in {v.strip() for v in product.split("|")} else "dangerous mismatch"
    elif metadata.get("image"):classification="likely compatible" if not device_codename else "insufficient metadata"
    return FirmwareAssessment(str(p),digest,len(data),classification,tuple(sorted(metadata.items())),tuple(warnings))
def readiness(identity,boot,recovery_goal=False):
    passed=[];blockers=[];warnings=[];unknowns=[]
    for key in ("codename","fingerprint","patch","architecture"):
        (passed if identity.get(key) else unknowns).append(key)
    if boot.get("locked") is True:warnings.append("Bootloader is locked; an authorized unlock commonly performs a factory reset.")
    if boot.get("oem_unlock_visible") in {"0","false"}:blockers.append("OEM unlocking is unavailable or disabled.")
    if recovery_goal:blockers.append("Bootloader unlocking must not be recommended as a data-recovery step because it commonly wipes data.")
    if boot.get("verified_boot")=="unknown":unknowns.append("verified boot state")
    return ReadinessMatrix(tuple(passed),tuple(blockers),tuple(warnings),tuple(unknowns),boot.get("locked") is not False,("adb shell getprop","fastboot getvar all  # preview only"))
def deterministic_report(identity,boot,matrix):return json.dumps({"identity":identity,"boot":boot,"readiness":asdict(matrix)},indent=2,sort_keys=True)+"\n"
def report_section(_context=None):return {"title":"Bootloader Readiness","body":"Read-only observations and operator-reviewed prerequisites; no command execution."}
def panel_spec(_context=None):
    names=("Device Identity","Boot Chain","Partitions","Root State","Firmware Inputs","Readiness","Plan")
    return PluginPanelSpec("Rootability & Bootloader Readiness Advisor",tuple(PluginView(n,"No device or firmware input is selected.",warning="Unlocking commonly wipes data and is never a recovery step.") for n in names),{"Selected device":"None","Mode":"Advisory only","Execution":"Disabled"})
class Plugin:
    def activate(self,api):self.api=api;return (Contribution("rootability.dashboard","dashboard-card","Rootability Advisor",factory=panel_spec),Contribution("rootability.panel","pentest-panel","Rootability Advisor",factory=panel_spec),Contribution("rootability.menu","menu-action","Open Rootability Advisor",metadata={"target":"rootability.panel"}),Contribution("rootability.report","report-section","Bootloader Readiness",factory=report_section,capability_requirement="contribute-report-section"),Contribution("rootability.finding","finding-template","Device Hardening Observation"))
    def deactivate(self):self.api=None
