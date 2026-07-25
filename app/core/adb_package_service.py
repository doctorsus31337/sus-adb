"""Selected-device package inspection and scope-guarded management."""
from __future__ import annotations
import re
from dataclasses import dataclass
from app.core.adb_explorer_models import PackageRecord
from app.core.command_result import CommandResult
from app.core.environment_change import EnvironmentChange
from app.core.pentest_event import EventCategory,PentestEvent
@dataclass(frozen=True,slots=True)
class ExplorerResult:
 ok:bool;value:object=None;result:CommandResult|None=None;error:str|None=None;preview:tuple[str,...]=();warning:str|None=None
class ADBPackageService:
 def __init__(self,adb,session_provider=lambda:None,timeline_provider=lambda:None,change_provider=lambda:None):self.adb=adb;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.change_provider=change_provider;self.cache=()
 def _need(self,serial,package=None):
  if not serial:return "No device is selected."
  if package is not None and (not package.strip() or any(c in package for c in "*?\n\0")):return "An explicit package identifier is required."
 def list_packages(self,serial,kind="all"):
  if (e:=self._need(serial)):return ExplorerResult(False,error=e)
  flag={"user":"-3","system":"-s"}.get(kind.casefold());args=["shell","pm","list","packages","-f"]+([flag] if flag else []);r=self.adb.run(*args,serial=serial)
  if not r.ok:return ExplorerResult(False,result=r,error=r.output)
  self.cache=tuple(PackageRecord(line.rsplit("=",1)[-1].strip(),apk_paths=(line[8:].rsplit("=",1)[0],),system="/system/" in line,serial=serial) for line in r.stdout.splitlines() if line.startswith("package:") and "=" in line);return ExplorerResult(True,self.cache,r)
 def search(self,q="",kind="all"):
  q=q.casefold();return tuple(p for p in self.cache if (kind=="all" or (kind=="system")==p.system) and q in (p.identifier+p.label).casefold())
 def inspect(self,serial,package):
  if (e:=self._need(serial,package)):return ExplorerResult(False,error=e)
  dump=self.adb.run("shell","dumpsys","package",package,serial=serial);paths=self.adb.run("shell","pm","path",package,serial=serial)
  if not dump.ok:return ExplorerResult(False,result=dump,error=dump.output)
  text=dump.stdout;find=lambda pattern:(re.search(pattern,text,re.M).group(1).strip() if re.search(pattern,text,re.M) else "")
  requested=tuple(re.findall(r"^\s{4}([\w.]+)$",text[text.find("requested permissions:"):text.find("install permissions:") if "install permissions:" in text else len(text)],re.M));granted=tuple(re.findall(r"^\s+([\w.]+): granted=true",text,re.M))
  item=PackageRecord(package,version_name=find(r"versionName=([^\s]+)"),version_code=find(r"versionCode=(\d+)"),uid=find(r"userId=(\d+)"),enabled="enabled=false" not in text,system="SYSTEM" in text,debuggable="DEBUGGABLE" in text,data_directory=find(r"dataDir=([^\s]+)"),apk_paths=tuple(l.split(":",1)[1] for l in paths.stdout.splitlines() if l.startswith("package:")),installer=find(r"installerPackageName=([^\s]+)"),requested_permissions=requested,granted_permissions=granted,first_install_time=find(r"firstInstallTime=(.+)"),last_update_time=find(r"lastUpdateTime=(.+)"),serial=serial);return ExplorerResult(True,item,dump)
 def build(self,serial,action,package="",value=""):
  adb=self.adb.adb_path or "adb";base=(adb,"-s",serial)
  commands={"install":(*base,"install",value),"uninstall":(*base,"uninstall",package),"force-stop":(*base,"shell","am","force-stop",package),"clear-data":(*base,"shell","pm","clear",package),"enable":(*base,"shell","pm","enable",package),"disable":(*base,"shell","pm","disable-user",package),"grant":(*base,"shell","pm","grant",package,value),"revoke":(*base,"shell","pm","revoke",package,value)};return commands[action]
 def execute(self,serial,action,package="",value="",confirmed=False,typed_confirmation=""):
  if (e:=self._need(serial,package if action!="install" else None)):return ExplorerResult(False,error=e)
  destructive=action in {"uninstall","clear-data"};category="apk-analysis" if action=="install" else "destructive-testing" if destructive else "state-changing-testing";session=self.session_provider()
  if not session or not session.permits(category):return ExplorerResult(False,error=f"Active authorized scope does not permit {category}.",preview=self.build(serial,action,package,value))
  if not confirmed:return ExplorerResult(False,error="Explicit confirmation is required.",preview=self.build(serial,action,package,value))
  if destructive and typed_confirmation!=package:return ExplorerResult(False,error="Typed package confirmation does not match.",preview=self.build(serial,action,package,value))
  command=self.build(serial,action,package,value);r=self.adb.run(*command[3:],serial=serial)
  if r.ok:
   timeline=self.timeline_provider();
   if timeline:timeline.append(PentestEvent(EventCategory.COMMAND,"adb-explorer",f"Package {action}",package,payload={"argv":command,"confirmation":typed_confirmation or True}))
   tracker=self.change_provider();
   if tracker and action not in {"clear-data","uninstall","force-stop"}:tracker.register(EnvironmentChange("package",f"Package {action}: {package}",device_serial=serial,target_identifier=package,restoration_instructions=f"Review and reverse package {action} manually.",restoration_command_preview=" ".join(command)))
  return ExplorerResult(r.ok,r.stdout,r,r.output if not r.ok else None,command)
