from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
REQUIRED=("VERSION","app/themes","docs","plugins/examples")
EXCLUDED=("flutter_popup_bypass.js","flutter_popup_bypass.meta.json")
def verify(root):
 root=Path(root);resource_root=root/"_internal" if (root/"_internal").is_dir() else root
 missing=tuple(v for v in REQUIRED if not (resource_root/v).exists())
 executable=next((p for p in (root/"sus-adb",root/"sus-adb.exe") if p.exists()),None)
 if executable is None:missing+=("sus-adb executable",)
 if not any(part in root.name for part in ("linux","windows")):missing+=("platform-qualified package name",)
 unexpected=tuple(name for name in EXCLUDED if any(p.name==name for p in root.rglob("*")))
 integrity=[];manifest_path=root/"release-manifest.json"
 try:
  manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
  listed={entry["path"] for entry in manifest["files"]}
  for entry in manifest["files"]:
   path=root/entry["path"]
   if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry["sha256"] or path.stat().st_size!=entry["size"]:integrity.append(entry["path"])
  actual={path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name not in {"release-manifest.json","SHA256SUMS"}}
  integrity.extend(f"unlisted:{path}" for path in sorted(actual-listed));integrity.extend(f"missing:{path}" for path in sorted(listed-actual))
  sums={line.split("  ",1)[1]:line.split("  ",1)[0] for line in (root/"SHA256SUMS").read_text(encoding="utf-8").splitlines() if "  " in line}
  if sums!={entry["path"]:entry["sha256"] for entry in manifest["files"]}:integrity.append("SHA256SUMS")
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):integrity.append("release-manifest.json")
 return {"ok":not missing and not unexpected and not integrity,"root":root.name,"resource_root":resource_root.name,"missing":missing,"excluded_present":unexpected,"integrity_errors":tuple(integrity)}
if __name__=="__main__":
 result=verify(sys.argv[1] if len(sys.argv)>1 else "dist/sus-adb-1.0.0-rc.1-linux-x86_64");print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result["ok"] else 1)
