"""Default-deny plugin capability authorization."""
from dataclasses import dataclass
CAPABILITIES=("read-selected-device","read-selected-target","run-adb-readonly","run-adb-state-changing","access-frida-runtime","load-frida-script","access-active-case","append-timeline","read-evidence-metadata","create-evidence","read-findings","create-findings","contribute-report-section","read-local-plugin-files","write-plugin-state","launch-external-terminal","access-network","access-host-processes","modify-device-state","destructive-device-action")
HIGH_IMPACT=frozenset(("run-adb-state-changing","load-frida-script","create-evidence","create-findings","launch-external-terminal","access-network","access-host-processes","modify-device-state","destructive-device-action"))
SCOPE_REQUIREMENTS={"run-adb-state-changing":"state-changing-testing","load-frida-script":"script-execution","create-evidence":"evidence-collection","create-findings":"evidence-collection","modify-device-state":"state-changing-testing","destructive-device-action":"destructive-testing"}
@dataclass(frozen=True,slots=True)
class PermissionResult:
    allowed:bool;capability:str;error:str|None=None;caution:str|None=None
class CapabilityPolicy:
    def __init__(self,approved=()):self.approved=frozenset(approved)
    def check(self,capability,session=None):
        if capability not in CAPABILITIES:return PermissionResult(False,capability,"Unknown plugin capability.")
        if capability not in self.approved:return PermissionResult(False,capability,"Capability was not explicitly approved for this plugin.")
        category=SCOPE_REQUIREMENTS.get(capability)
        if category and (not session or not session.permits(category)):return PermissionResult(False,capability,f"Active assessment scope does not permit {category}.")
        return PermissionResult(True,capability,caution="High-impact trusted-code capability." if capability in HIGH_IMPACT else None)
