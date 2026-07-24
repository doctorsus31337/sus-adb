from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
def build_metadata(root):
 for candidate in (root/"build-info.json",root/"_internal/build-info.json"):
  try:
   value=json.loads(candidate.read_text(encoding="utf-8"))
   return {key:value[key] for key in ("version","commit","short_commit","ref","timestamp","channel")}
  except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):continue
 return {}
def generate(root,output=None):
 root=Path(root).resolve();items=[]
 for p in sorted(v for v in root.rglob("*") if v.is_file() and v.name not in {"SHA256SUMS","release-manifest.json"}):
  items.append((p.relative_to(root).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size))
 manifest={"format":1,"build":build_metadata(root),"files":[{"path":p,"sha256":d,"size":s} for p,d,s in items]};out=Path(output or root/"release-manifest.json");out.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8");(root/"SHA256SUMS").write_text("".join(f"{d}  {p}\n" for p,d,_ in items),encoding="utf-8");return manifest
if __name__=="__main__":generate(sys.argv[1])
