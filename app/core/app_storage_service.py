"""Selected-package storage discovery coordinating existing ADB services."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path
from app.core.adb_explorer_models import AccessMethod
from app.core.pentest_event import EventCategory,PentestEvent
from app.core.storage_models import AppStorageLocation,StorageAccessMode,StorageLocationType

@dataclass(frozen=True,slots=True)
class StorageResult:
 ok:bool;value:object=None;error:str|None=None;warning:str|None=None;preview:tuple[str,...]=()

class AppStorageService:
 def __init__(self,adb,file_service,package_service,session_provider=lambda:None,timeline_provider=lambda:None,evidence_provider=lambda:None,open_files_callback=None):self.adb=adb;self.files=file_service;self.packages=package_service;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.open_files_callback=open_files_callback;self.serial="";self.package="";self.locations=()
 def select(self,serial,package):
  if (serial or "",package or "")!=(self.serial,self.package):self.serial=serial or "";self.package=package or "";self.locations=()
 def _require(self,sensitive=True,category="storage-inspection"):
  if not self.serial or not self.package:return "An explicitly selected device and package are required."
  if sensitive:
   session=self.session_provider()
   if not session or not session.permits(category):return f"An active authorized assessment permitting {category} is required."
   if session.scope.device_serial!=self.serial or session.scope.package_identifier!=self.package:return "Selected device/package does not match the active scope."
  return None
 def readiness(self):
  if (e:=self._require(False)):return StorageResult(False,error=e)
  run_as=self.adb.run("shell","run-as",self.package,"id",serial=self.serial,timeout=10);root=self.adb.run("shell","su","-c","id",serial=self.serial,timeout=10)
  return StorageResult(True,{"run_as":run_as.ok,"root":root.ok and "uid=0" in root.stdout})
 def discover(self):
  if (e:=self._require()):return StorageResult(False,error=e)
  inspected=self.packages.inspect(self.serial,self.package)
  data=inspected.value.data_directory if inspected.ok and inspected.value.data_directory else f"/data/user/0/{self.package}";ready=self.readiness().value or {}
  mode=StorageAccessMode.RUN_AS if ready.get("run_as") else StorageAccessMode.ROOT if ready.get("root") else StorageAccessMode.NORMAL
  self.locations=(AppStorageLocation(self.serial,self.package,"Application data",data,StorageLocationType.DATA,mode,ready.get("run_as") or ready.get("root"),False,"sensitive"),AppStorageLocation(self.serial,self.package,"Device-protected data",f"/data/user_de/0/{self.package}",StorageLocationType.DEVICE_PROTECTED_DATA,mode,ready.get("run_as") or ready.get("root"),False,"sensitive"),AppStorageLocation(self.serial,self.package,"External files",f"/sdcard/Android/data/{self.package}/files",StorageLocationType.EXTERNAL_FILES,StorageAccessMode.NORMAL,True,True,"internal"),AppStorageLocation(self.serial,self.package,"External cache",f"/sdcard/Android/data/{self.package}/cache",StorageLocationType.EXTERNAL_CACHE,StorageAccessMode.NORMAL,True,True,"internal"),AppStorageLocation(self.serial,self.package,"Shared storage","/sdcard",StorageLocationType.SHARED_STORAGE,StorageAccessMode.NORMAL,True,True,"public"))
  self._event("Storage locations discovered",f"{self.package}: {len(self.locations)} locations");return StorageResult(True,self.locations)
 def browse(self,location):
  private=location.location_type in (StorageLocationType.DATA,StorageLocationType.DEVICE_PROTECTED_DATA)
  if (e:=self._require(private)):return StorageResult(False,error=e,warning="Not recorded in an active assessment." if not private else None)
  mode={StorageAccessMode.NORMAL:AccessMethod.NORMAL,StorageAccessMode.RUN_AS:AccessMethod.RUN_AS,StorageAccessMode.ROOT:AccessMethod.ROOT}[location.access_mode];r=self.files.list_directory(self.serial,location.remote_path,mode,self.package);self._event("Private storage browsed" if private else "Shared storage browsed",location.remote_path) if r.ok else None;return StorageResult(r.ok,r.value,r.error,r.warning)
 def pull(self,remote,destination,overwrite=False):
  if (e:=self._require()):return StorageResult(False,error=e)
  r=self.files.pull(self.serial,remote,destination,overwrite=overwrite);self._event("Storage artifact pulled",remote) if r.ok else None;return StorageResult(r.ok,r.value,r.error)
 def local_hash(self,path):
  p=Path(path).expanduser().resolve()
  if not p.is_file():return StorageResult(False,error="Select an existing local file.")
  return StorageResult(True,hashlib.sha256(p.read_bytes()).hexdigest())
 def add_to_evidence(self,path,remote_path=""):
  if (e:=self._require(category="evidence-collection")):return StorageResult(False,error=e)
  store=self.evidence_provider();r=store.import_file(path,title=Path(path).name,description=f"Collected explicitly from {remote_path}" if remote_path else "Explicitly selected storage artifact",device_serial=self.serial,target_identifier=self.package) if store else None
  return StorageResult(bool(r and r.ok),r.item if r and r.ok else None,getattr(r,"error","No active evidence store."))
 def open_in_adb_explorer(self,path):
  if self.open_files_callback:self.open_files_callback(path);return StorageResult(True,path)
  return StorageResult(False,error="ADB Explorer navigation is unavailable.")
 def clear(self):self.locations=()
 def _event(self,title,description):
  timeline=self.timeline_provider()
  if timeline:timeline.append(PentestEvent(EventCategory.STORAGE,"storage-explorer",title,description,related_target_identifier=self.package))
