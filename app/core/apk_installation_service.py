from __future__ import annotations
from app.core.environment_change import EnvironmentChange
from app.core.pentest_event import EventCategory,PentestEvent
class ApkInstallationService:
 def __init__(self,adb,session_provider=lambda:None,timeline_provider=lambda:None,change_provider=lambda:None):self.adb=adb;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.change_provider=change_provider
 def preview(self,serial,paths,replace=False,downgrade=False):
  cmd=[self.adb.adb_path or "adb","-s",serial,"install-multiple" if len(paths)>1 else "install"]
  if replace:cmd.append("-r")
  if downgrade:cmd.append("-d")
  return tuple(cmd)+tuple(map(str,paths))
 def install(self,serial,package,artifacts,confirmed=False,typed="",replace=False,downgrade=False):
  session=self.session_provider()
  if not serial:return (False,"Explicit selected serial is required.")
  if not artifacts or any(a.artifact_type.value!="signed-apk" for a in artifacts):return (False,"Only signed APK artifacts may be installed.")
  if not session or not (session.permits("apk-analysis") or session.permits("state-changing-testing")):return (False,"Active authorized APK scope is required.")
  if not confirmed or (replace and typed!=package):return (False,"Explicit confirmation and matching typed package are required.")
  preview=self.preview(serial,[a.source_path for a in artifacts],replace,downgrade);r=self.adb.run(*preview[3:],serial=serial)
  if r.ok:
   t=self.timeline_provider();c=self.change_provider()
   if t:t.append(PentestEvent(EventCategory.APK,"apk-lab","Test build installed",package,payload={"argv":preview}))
   if c:c.register(EnvironmentChange("apk-install","APK Lab test build installed",package,serial,package,restoration_instructions="Uninstall the test build or reinstall the preserved original.",restoration_command_preview=f"adb -s {serial} uninstall {package}"))
  return (r.ok,r.output)
 def launch(self,serial,package,confirmed=False):return (False,"Separate launch confirmation is required.") if not confirmed else (self.adb.run("shell","monkey","-p",package,"1",serial=serial).ok,package)
