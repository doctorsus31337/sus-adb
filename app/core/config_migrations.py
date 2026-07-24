"""Sequential, deterministic configuration migrations."""
from __future__ import annotations
import copy
from app.core.config_schema import SCHEMA_VERSION
def migrate(data,target=SCHEMA_VERSION):
    result=copy.deepcopy(data);version=int(result.get("schema_version",1));applied=[]
    while version<target:
        if version==1:
            legacy_level=result.pop("log_level", "INFO")
            result.setdefault("privacy",{"log_level":legacy_level,"structured_logs":True,"redact_device_serials":True,"redact_local_paths":True,"retention_days":30});version=2
        elif version==2:
            result.setdefault("plugin_storage_root","plugins");result.setdefault("capture_defaults",{"duration":30,"maximum_duration":300});version=3
        elif version==3:
            result.setdefault("interface",{"mode":"advanced"});version=4
        else:raise ValueError(f"No migration exists from schema version {version}.")
        result["schema_version"]=version;applied.append(version)
    if version>target:raise ValueError("Configuration schema is newer than this application supports.")
    return result,tuple(applied)
