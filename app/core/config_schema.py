"""Versioned configuration defaults and validation."""
from __future__ import annotations
import copy,re
SCHEMA_VERSION=4
DEFAULTS={"schema_version":SCHEMA_VERSION,"appearance":{"theme":"gothic"},"interface":{"mode":"guided"},"window":{"geometry":"1400x860"},"addon_windows":{},"terminal":{"preference":"auto"},"executables":{},"adb_path":"adb","frida_endpoint":"127.0.0.1:27042","workspace_root":"workspaces","script_library_root":"scripts","script_studio":{"show_static_analysis_advisories":False},"plugin_storage_root":"plugins","report_defaults":{"classification":"Internal"},"capture_defaults":{"duration":30,"maximum_duration":300},"privacy":{"log_level":"INFO","structured_logs":True,"redact_device_serials":True,"redact_local_paths":True,"retention_days":30},"last_active_case":"","recent_projects":[]}
SECRET_KEYS=frozenset(("password","token","secret","private_key","keystore_password","credential"))
def defaults():return copy.deepcopy(DEFAULTS)
def validate(data):
    errors=[]
    if not isinstance(data,dict):return ("Configuration must be a JSON object.",)
    if not isinstance(data.get("schema_version",0),int):errors.append("schema_version must be an integer.")
    def secret_keys(value):
        if isinstance(value,dict):
            for key,nested in value.items():
                if str(key).casefold() in SECRET_KEYS:yield str(key)
                yield from secret_keys(nested)
        elif isinstance(value,(list,tuple)):
            for nested in value:yield from secret_keys(nested)
    if next(secret_keys(data),None) is not None:errors.append("Secrets and credentials may not be stored in configuration.")
    privacy=data.get("privacy",{})
    if privacy and not isinstance(privacy,dict):errors.append("privacy must be an object.")
    interface=data.get("interface",{})
    if not isinstance(interface,dict) or interface.get("mode","guided") not in {"guided","advanced"}:errors.append("interface.mode must be guided or advanced.")
    script_studio=data.get("script_studio",{})
    if not isinstance(script_studio,dict) or not isinstance(script_studio.get("show_static_analysis_advisories",False),bool):errors.append("script_studio.show_static_analysis_advisories must be a boolean.")
    geometries=data.get("addon_windows",{})
    if not isinstance(geometries,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch(r"\d+x\d+\+-?\d+\+-?\d+",v) for k,v in geometries.items()):errors.append("addon_windows must contain only numeric geometry values.")
    return tuple(errors)
