"""Central immutable release/build metadata."""
from __future__ import annotations
import os,platform,sys
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True,slots=True)
class AppMetadata:
    application_name:str="SUS Companion";display_mark:str="SUS COMPANION";descriptor:str="Android Security & Recovery Workstation";legacy_application_name:str="SUS-ADB Companion";preferred_executable:str="sus-companion";legacy_executable:str="sus-adb";version:str="1.0.0-rc.1";release_channel:str="rc";build_identifier:str="rc1";repository_revision:str="unknown";build_timestamp:str="reproducible";python_version:str=platform.python_version();platform_name:str=platform.system();architecture:str=platform.machine();plugin_api_version:str="1.0";configuration_schema_version:int=3;case_workspace_schema_version:int=1
    @property
    def display_version(self):return f"{self.application_name} {self.version} ({self.release_channel})"
    @classmethod
    def current(cls,version_file=None,environ=None):
        env=dict(environ or os.environ);path=Path(version_file or Path(__file__).resolve().parents[2]/"VERSION")
        try:version=path.read_text(encoding="utf-8").strip()
        except OSError:version="1.0.0-rc.1"
        return cls(version=version,build_identifier=env.get("SUS_ADB_BUILD_ID","rc1"),repository_revision=env.get("SUS_ADB_REVISION","unknown"),build_timestamp=env.get("SUS_ADB_BUILD_TIMESTAMP","reproducible"),python_version=platform.python_version(),platform_name=platform.system(),architecture=platform.machine())
METADATA=AppMetadata.current()

def create_metadata(**values):
    """Create deterministic metadata for builds and tests without probing Git."""
    return AppMetadata(**values)
