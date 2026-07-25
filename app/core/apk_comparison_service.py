from __future__ import annotations
import hashlib,json
from pathlib import Path
from app.core.apk_lab_models import ApkDifference,ApkDifferenceType
class ApkComparisonService:
 def __init__(self,max_files=10000,max_size=1_000_000_000):self.max_files=max_files;self.max_size=max_size;self.cancelled=False
 def manifest(self,root):
  root=Path(root).resolve();files={};total=0
  for p in sorted(root.rglob("*")):
   if p.is_symlink() or not p.is_file():continue
   total+=p.stat().st_size
   if len(files)>=self.max_files or total>self.max_size:raise ValueError("Comparison bounds exceeded.")
   files[p.relative_to(root).as_posix()]=(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size)
  return files
 def compare(self,a,b):
  x,y=self.manifest(a),self.manifest(b);out=[]
  for p in sorted(set(x)|set(y)):
   o,n=x.get(p),y.get(p);kind=ApkDifferenceType.ADDED if o is None else ApkDifferenceType.REMOVED if n is None else ApkDifferenceType.UNCHANGED if o[0]==n[0] else ApkDifferenceType.MODIFIED;out.append(ApkDifference(p,kind,o[0] if o else "",n[0] if n else "",o[1] if o else 0,n[1] if n else 0))
  return tuple(out)
 def export(self,path,diffs):Path(path).write_text(json.dumps([d.to_dict() for d in diffs],indent=2,sort_keys=True),encoding="utf-8");return path
 def cancel(self):self.cancelled=True
