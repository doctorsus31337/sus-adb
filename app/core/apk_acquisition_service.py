from __future__ import annotations
import zipfile
from pathlib import Path,PurePosixPath
from app.core.apk_lab_models import ApkArtifactType,ApkSetRecord
class ApkAcquisitionService:
 def __init__(self,adb,packages,workspace,session_provider=lambda:None,timeline_provider=lambda:None,evidence_provider=lambda:None):self.adb=adb;self.packages=packages;self.workspace=workspace;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider
 def inspect_paths(self,serial,package):return self.packages.inspect(serial,package)
 def pull(self,serial,package,paths,confirmed=False):
  session=self.session_provider()
  if not serial or not package:return (False,"Explicit selected serial and package are required.")
  if not session or not session.permits("apk-analysis"):return (False,"Active apk-analysis scope is required.")
  if not confirmed:return (False,"Explicit pull confirmation is required.")
  artifacts=[]
  for i,path in enumerate(paths):
   dest=self.workspace.safe(Path("originals")/Path(path).name);r=self.adb.run("pull",path,str(dest),serial=serial)
   if not r.ok:return (False,r.output)
   artifacts.append(self.workspace.import_file(dest,ApkArtifactType.BASE if i==0 else ApkArtifactType.SPLIT,package,destination_group="originals",device_serial=serial,target_identifier=package))
  return (True,ApkSetRecord(package,artifacts[0] if artifacts else None,tuple(artifacts[1:]),complete=bool(artifacts),device_serial=serial))
 def import_local(self,path,package=""):return self.workspace.import_file(path,ApkArtifactType.IMPORTED,package)
 def inspect_container(self,path):
  with zipfile.ZipFile(path) as z:
   names=tuple(i.filename for i in z.infolist())
   if any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts for n in names):raise ValueError("Archive traversal was rejected.")
   return names
