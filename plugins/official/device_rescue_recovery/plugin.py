"""Authorized, selected-file recovery logic. No operation runs during activation."""
from __future__ import annotations
from app.core.device_recovery_service import (
    PUBLIC_PRESETS,
    RecoveryEngine,
    RecoveryItem,
    RecoveryLimits,
    RecoveryResult,
    manifest,
    public_paths,
)
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_ui import PluginPanelSpec,PluginView

DEVICE_STATES=("device","recovery","sideload","bootloader","fastbootd","unauthorized","offline","unavailable")
OUTCOMES=("Ready for authorized recovery","ADB authorization required on device","Device available through public shared storage","Recovery ADB available","Existing root permits selected private-path recovery","Device is encrypted and locked; existing authentication is required","Interactive access or screen replacement is required","MTP/manual recovery may be available","Bootloader unlocking would wipe data and must not be used for recovery","No safe software-only recovery path currently available")

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

def report_section(_context=None):return {"title":"Recovery Results","body":"Operator-selected recovery results only; evidence registration is always explicit."}
def panel_spec(context=None):
    names=("Overview","Connection","Storage Scan","Recovery Plan","Files","Copy Queue","Results","Guidance")
    selected=getattr(context,"selected_device",{}) or {};serial=selected.get("serial","");state=selected.get("state","unavailable")
    status={"Selected device":selected.get("display_name") or serial or "None","Serial":serial or "None","ADB state":getattr(context,"adb_state",state).title(),"Authorization":"Authorized" if selected.get("authorized") else "Unavailable","Queued files":"0","Bytes planned":"0","Recovered":"0","Skipped":"0","Failed":"0","Manifest":"Not created"}
    body=f"Selected serial: {serial}\nConnection state: {state}" if serial else "No device is explicitly selected. Refresh and choose a device before planning recovery."
    return PluginPanelSpec("Device Rescue & Recovery",tuple(PluginView(name,body,warning="Bootloader unlocking commonly wipes data and must not be used for recovery.") for name in names),status)
class Plugin:
    def activate(self,api):
        self.api=api
        return (Contribution("device-rescue.dashboard","dashboard-card","Device Rescue & Recovery",factory=panel_spec),Contribution("device-rescue.panel","pentest-panel","Device Rescue & Recovery",factory=panel_spec,metadata={"ui_mode":"window","singleton":True,"device_selector":True,"workspace_kind":"device-recovery"}),Contribution("device-rescue.menu","menu-action","Open Device Rescue",metadata={"target":"device-rescue.panel"}),Contribution("device-rescue.report","report-section","Recovery Results",factory=report_section,capability_requirement="contribute-report-section"),Contribution("device-rescue.manifest","evidence-processor","Recovery Manifest Exporter"))
    def deactivate(self):self.api=None
