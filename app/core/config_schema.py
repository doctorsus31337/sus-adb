"""Versioned configuration defaults and validation."""
from __future__ import annotations
import copy
SCHEMA_VERSION=3
DEFAULTS={"schema_version":SCHEMA_VERSION,"appearance":{"theme":"gothic"},"window":{"geometry":"1400x860"},"terminal":{"preference":"auto"},"executables":{},"adb_path":"adb","frida_endpoint":"127.0.0.1:27042","workspace_root":"workspaces","script_library_root":"scripts","plugin_storage_root":"plugins","report_defaults":{"classification":"Internal"},"capture_defaults":{"duration":30,"maximum_duration":300},"privacy":{"log_level":"INFO","structured_logs":True,"redact_device_serials":True,"redact_local_paths":True,"retention_days":30},"last_active_case":"","recent_projects":[]}
SECRET_KEYS=frozenset(("password","token","secret","private_key","keystore_password","credential"))
def defaults():return copy.deepcopy(DEFAULTS)
def validate(data):
    errors=[]
    if not isinstance(data,dict):return ("Configuration must be a JSON object.",)
    if not isinstance(data.get("schema_version",0),int):errors.append("schema_version must be an integer.")
    if any(str(k).casefold() in SECRET_KEYS for k in data):errors.append("Secrets and credentials may not be stored in configuration.")
    privacy=data.get("privacy",{})
    if privacy and not isinstance(privacy,dict):errors.append("privacy must be an object.")
    return tuple(errors)
