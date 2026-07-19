"""Isolated, original-preserving APK artifact workspace."""
from __future__ import annotations
import hashlib,json,shutil
from pathlib import Path
from app.core.apk_lab_models import ApkArtifact,ApkArtifactType
class ApkWorkspaceService:
 LAYOUT=("originals","imported","decoded","decompiled","modified","rebuilt","aligned","signed","gadget","manifests","comparisons","exports","temporary")
 def __init__(self,root):self.root=Path(root).resolve();self.artifacts=[]
 def initialize(self):
  for n in self.LAYOUT:(self.root/n).mkdir(parents=True,exist_ok=True)
  return self.root
 def safe(self,path):
  p=(self.root/path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
  if p!=self.root and self.root not in p.parents:raise ValueError("Path escapes APK Lab workspace.")
  return p
 def import_file(self,source,kind=ApkArtifactType.IMPORTED,package="",parent_id=None,destination_group="imported",device_serial="",target_identifier=""):
  src=Path(source).expanduser().resolve()
  if not src.is_file():raise ValueError("Select an existing APK artifact.")
  data=src.read_bytes();digest=hashlib.sha256(data).hexdigest()
  if any(a.sha256==digest for a in self.artifacts):raise ValueError("Duplicate artifact content already exists.")
  self.initialize();dest=self.safe(Path(destination_group)/f"{digest[:12]}-{src.name}")
  if dest.exists():raise ValueError("Destination exists; overwrite is forbidden.")
  shutil.copy2(src,dest);artifact=ApkArtifact(kind,str(src),dest.relative_to(self.root).as_posix(),digest,len(data),package,parent_artifact_id=parent_id,device_serial=device_serial,target_identifier=target_identifier);self.artifacts.append(artifact);return artifact
 def list(self,query="",kind="All"):
  q=query.casefold();return tuple(a for a in self.artifacts if (kind=="All" or a.artifact_type.value==kind) and (not q or q in a.display_label.casefold()))
 def delete_derived(self,artifact,confirmed=False):
  if artifact.artifact_type in (ApkArtifactType.BASE,ApkArtifactType.SPLIT,ApkArtifactType.IMPORTED) or not confirmed:return False
  p=self.safe(artifact.workspace_relative_path);shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True);self.artifacts.remove(artifact);return True
 def export_manifest(self,path,markdown=False):
  p=self.safe(path)
  if p.exists():raise ValueError("Destination exists.")
  values=sorted(self.artifacts,key=lambda a:a.artifact_id);text="# APK Artifact Manifest\n\n"+"\n".join(f"- {a.display_label}" for a in values) if markdown else json.dumps([a.to_dict() for a in values],indent=2,sort_keys=True);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding="utf-8");return p
