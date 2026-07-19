"""Explicit-mode remote Android filesystem operations."""
from __future__ import annotations
import hashlib,os,posixpath,re,shlex
from pathlib import Path
from app.core.adb_explorer_models import AccessMethod,RemoteEntryType,RemoteFileEntry
from app.core.adb_package_service import ExplorerResult
from app.core.environment_change import EnvironmentChange
from app.core.pentest_event import EventCategory,PentestEvent

class ADBFileService:
    def __init__(self,adb,session_provider=lambda:None,timeline_provider=lambda:None,evidence_provider=lambda:None,change_provider=lambda:None):self.adb=adb;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.change_provider=change_provider
    @staticmethod
    def _valid(path):return bool(path and path.startswith("/") and "\0" not in path)
    @staticmethod
    def _remote(command,mode,package):
        if mode is AccessMethod.RUN_AS:
            if not package:raise ValueError("run-as requires an explicit package.")
            return ("shell","run-as",package,"sh","-c",command)
        if mode is AccessMethod.ROOT:return ("shell","su","-c",command)
        return ("shell","sh","-c",command)
    def _guard(self,serial,path,mode,package="",changing=False,sensitive=False,destructive=False,confirmed=False,typed=""):
        if not serial:return "No device is selected."
        if not self._valid(path):return "A non-empty absolute remote path is required."
        if mode is AccessMethod.RUN_AS and not package:return "run-as requires an explicit selected package."
        if changing or sensitive:
            session=self.session_provider();categories=("state-changing-testing",) if changing else ("sensitive-data-inspection","storage-inspection")
            if not session or not any(session.permits(c) for c in categories):return f"Active scope does not permit {' or '.join(categories)}."
        if destructive and (not confirmed or typed!=path):return "Explicit full-path typed confirmation is required."
    def list_directory(self,serial,path,mode=AccessMethod.NORMAL,package=""):
        mode=AccessMethod(mode)
        if (e:=self._guard(serial,path,mode,package,sensitive=mode is not AccessMethod.NORMAL)):return ExplorerResult(False,error=e)
        command=f"ls -la -- {shlex.quote(path)}";r=self.adb.run(*self._remote(command,mode,package),serial=serial)
        return ExplorerResult(r.ok,self.parse_ls(r.stdout,path,mode,serial,package),r,r.output if not r.ok else None)
    @staticmethod
    def parse_ls(text,parent,mode,serial="",package=""):
        items=[]
        for line in text.splitlines():
            parts=line.split(None,7)
            if len(parts)<8 or parts[0].startswith("total"):continue
            perm,owner,group,size,modified,name=parts[0],parts[2],parts[3],parts[4]," ".join(parts[5:7]),parts[7];target=""
            if " -> " in name:name,target=name.split(" -> ",1)
            kind=RemoteEntryType.DIRECTORY if perm.startswith("d") else RemoteEntryType.SYMLINK if perm.startswith("l") else RemoteEntryType.FILE if perm.startswith("-") else RemoteEntryType.UNKNOWN
            try:nsize=int(size)
            except ValueError:nsize=None
            items.append(RemoteFileEntry(name,posixpath.join(parent,name),kind,nsize,perm,owner,group,modified,target,mode,serial,package))
        return tuple(items)
    def metadata(self,serial,path,mode=AccessMethod.NORMAL,package=""):
        mode=AccessMethod(mode)
        if (e:=self._guard(serial,path,mode,package,sensitive=mode is not AccessMethod.NORMAL)):return ExplorerResult(False,error=e)
        r=self.adb.run(*self._remote(f"stat -- {shlex.quote(path)}",mode,package),serial=serial);return ExplorerResult(r.ok,r.stdout,r,r.output if not r.ok else None)
    def remote_hash(self,serial,path,mode=AccessMethod.NORMAL,package=""):
        mode=AccessMethod(mode)
        if (e:=self._guard(serial,path,mode,package,sensitive=mode is not AccessMethod.NORMAL)):return ExplorerResult(False,error=e)
        r=self.adb.run(*self._remote(f"sha256sum -- {shlex.quote(path)}",mode,package),serial=serial);return ExplorerResult(r.ok,r.stdout.split()[0] if r.ok and r.stdout else "",r,r.output if not r.ok else None)
    def pull(self,serial,path,destination,overwrite=False,add_evidence=False):
        if (e:=self._guard(serial,path,AccessMethod.NORMAL,sensitive=True)):return ExplorerResult(False,error=e)
        dest=Path(destination).expanduser().resolve()
        if dest.exists() and not overwrite:return ExplorerResult(False,error="Local destination exists; overwrite was not authorized.")
        r=self.adb.run("pull",path,str(dest),serial=serial)
        if r.ok and add_evidence:
            store=self.evidence_provider()
            if store:store.import_file(dest,original_source=path,device_serial=serial)
        return ExplorerResult(r.ok,str(dest),r,r.output if not r.ok else None)
    def push(self,serial,local,path,confirmed=False,package=""):
        if (e:=self._guard(serial,path,AccessMethod.NORMAL,package,changing=True,confirmed=confirmed)):return ExplorerResult(False,error=e)
        src=Path(local).expanduser().resolve()
        if not src.is_file():return ExplorerResult(False,error="Select an existing local file.")
        if not confirmed:return ExplorerResult(False,error="Explicit push confirmation is required.")
        r=self.adb.run("push",str(src),path,serial=serial);self._record(serial,package,"Remote file uploaded",path,f"rm -- {shlex.quote(path)}",r.ok);return ExplorerResult(r.ok,r.stdout,r,r.output if not r.ok else None)
    def mutate(self,serial,operation,path,new_path="",mode=AccessMethod.NORMAL,package="",confirmed=False,typed=""):
        mode=AccessMethod(mode);destructive=operation=="delete"
        if destructive and path in {"/",""}:return ExplorerResult(False,error="Deleting an empty path or filesystem root is forbidden.")
        if (e:=self._guard(serial,path,mode,package,changing=True,destructive=destructive,confirmed=confirmed,typed=typed)):return ExplorerResult(False,error=e)
        if not confirmed:return ExplorerResult(False,error="Explicit confirmation is required.")
        if operation in {"rename","mkdir"} and not self._valid(new_path):return ExplorerResult(False,error="A valid absolute destination path is required.")
        commands={"mkdir":f"mkdir -- {shlex.quote(new_path)}","rename":f"mv -- {shlex.quote(path)} {shlex.quote(new_path)}","delete":f"rm -r -- {shlex.quote(path)}"}
        if operation not in commands:return ExplorerResult(False,error="Unsupported file operation.")
        command=commands[operation];r=self.adb.run(*self._remote(command,mode,package),serial=serial);self._record(serial,package,f"Remote {operation}",path,"Restore from backup or remove the uploaded path manually.",r.ok,destructive);return ExplorerResult(r.ok,r.stdout,r,r.output if not r.ok else None,tuple(self._remote(command,mode,package)))
    def _record(self,serial,package,title,path,guidance,ok,destructive=False):
        if not ok:return
        timeline=self.timeline_provider()
        if timeline:timeline.append(PentestEvent(EventCategory.STORAGE,"adb-explorer",title,path,related_target_identifier=package))
        tracker=self.change_provider()
        if tracker:tracker.register(EnvironmentChange("remote-file",title,path,serial,package,restoration_instructions=guidance,destructive=destructive,reversible=not destructive))
