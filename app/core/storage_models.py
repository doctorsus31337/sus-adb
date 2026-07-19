"""Immutable models for authorized Android storage analysis."""
from __future__ import annotations
import uuid
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from enum import Enum

def now():return datetime.now(timezone.utc).isoformat()
class StorageLocationType(str,Enum):DATA="data";DEVICE_PROTECTED_DATA="device-protected-data";EXTERNAL_FILES="external-files";EXTERNAL_CACHE="external-cache";SHARED_STORAGE="shared-storage";CUSTOM="custom"
class StorageAccessMode(str,Enum):NORMAL="normal-shell";RUN_AS="run-as";ROOT="root"
class DifferenceStatus(str,Enum):ADDED="added";REMOVED="removed";MODIFIED="modified";UNCHANGED="unchanged"

@dataclass(frozen=True,slots=True)
class AppStorageLocation:
 device_serial:str;target_identifier:str;label:str;remote_path:str;location_type:StorageLocationType=StorageLocationType.CUSTOM;access_mode:StorageAccessMode=StorageAccessMode.NORMAL;readable:bool=False;writable:bool=False;sensitivity:str="internal"
 def __post_init__(self):object.__setattr__(self,"location_type",StorageLocationType(self.location_type));object.__setattr__(self,"access_mode",StorageAccessMode(self.access_mode))
 @property
 def display_label(self):return f"{self.label} · {self.remote_path} · {self.access_mode.value} · {'readable' if self.readable else 'unreadable'} · {self.sensitivity}"
 def to_dict(self):d=asdict(self);d["location_type"]=self.location_type.value;d["access_mode"]=self.access_mode.value;return d
@dataclass(frozen=True,slots=True)
class SharedPreferenceEntry:
 source_file:str;key:str;value_type:str;value_preview:str;full_value:object=None;namespace:str="";device_serial:str="";target_identifier:str="";sensitive_label:str="unclassified"
 @property
 def display_label(self):return f"{self.namespace or self.source_file} · {self.key} [{self.value_type}] · {self.value_preview} · {self.sensitive_label}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class SQLiteDatabaseRecord:
 remote_path:str;local_working_path:str="";file_size:int=0;sha256:str="";encrypted_or_unreadable:bool=False;wal_paths:tuple[str,...]=();table_count:int=0;device_serial:str="";target_identifier:str=""
 def __post_init__(self):object.__setattr__(self,"wal_paths",tuple(self.wal_paths))
 @property
 def display_label(self):return f"{self.remote_path} · {self.file_size} bytes · {self.table_count} objects · {self.sha256 or 'unhashed'}{' · encrypted/unreadable' if self.encrypted_or_unreadable else ''}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class SQLiteColumnRecord:
 table_name:str;column_name:str;declared_type:str="";nullable:bool=True;default_value:object=None;primary_key_order:int=0
 @property
 def display_label(self):return f"{self.column_name} {self.declared_type} · {'NULL' if self.nullable else 'NOT NULL'} · PK {self.primary_key_order or '-'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class SQLiteTableRecord:
 database_path:str;table_name:str;table_type:str="table";row_count_estimate:int|None=None;columns:tuple[SQLiteColumnRecord,...]=();primary_keys:tuple[str,...]=();foreign_keys:tuple[dict,...]=();indexes:tuple[dict,...]=()
 def __post_init__(self):object.__setattr__(self,"columns",tuple(self.columns));object.__setattr__(self,"primary_keys",tuple(self.primary_keys));object.__setattr__(self,"foreign_keys",tuple(dict(v) for v in self.foreign_keys));object.__setattr__(self,"indexes",tuple(dict(v) for v in self.indexes))
 @property
 def display_label(self):return f"{self.table_type} · {self.table_name} · {len(self.columns)} columns · {self.row_count_estimate if self.row_count_estimate is not None else 'rows not counted'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class ContentProviderRecord:
 package_identifier:str;component_name:str;authority:str="";exported:bool|None=None;enabled:bool|None=None;read_permission:str="";write_permission:str="";grant_uri_permissions:bool=False;device_serial:str=""
 @property
 def display_label(self):return f"{self.authority or self.component_name} · exported={self.exported} · read={self.read_permission or 'none'} · write={self.write_permission or 'none'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class ContentQuerySpec:
 content_uri:str;projection:tuple[str,...]=();selection:str="";selection_arguments:tuple[str,...]=();sort_order:str="";row_limit:int=100
 def __post_init__(self):object.__setattr__(self,"projection",tuple(self.projection));object.__setattr__(self,"selection_arguments",tuple(self.selection_arguments))
 @property
 def display_label(self):return f"{self.content_uri} · limit {self.row_limit} · projection {', '.join(self.projection) or '*'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class StorageSnapshot:
 device_serial:str;target_identifier:str;source_paths:tuple[str,...];local_directory:str;file_count:int=0;total_size:int=0;manifest_path:str="";manifest_digest:str="";evidence_id:str|None=None;snapshot_id:str=field(default_factory=lambda:str(uuid.uuid4()));created_at:str=field(default_factory=now)
 def __post_init__(self):object.__setattr__(self,"source_paths",tuple(self.source_paths))
 @property
 def display_label(self):return f"{self.snapshot_id[:8]} · {self.file_count} files · {self.total_size} bytes · {self.manifest_digest or 'unhashed'}"
 def to_dict(self):return asdict(self)
@dataclass(frozen=True,slots=True)
class StorageDifference:
 relative_path:str;status:DifferenceStatus;old_digest:str="";new_digest:str="";old_size:int=0;new_size:int=0
 def __post_init__(self):object.__setattr__(self,"status",DifferenceStatus(self.status))
 @property
 def display_label(self):return f"{self.status.value} · {self.relative_path} · {self.old_size} → {self.new_size} bytes"
 def to_dict(self):d=asdict(self);d["status"]=self.status.value;return d
