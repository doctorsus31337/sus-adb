from __future__ import annotations
import json,sys
from pathlib import Path
REQUIRED=("VERSION","app/themes","docs","plugins/examples")
def verify(root):
 root=Path(root);resource_root=root/"_internal" if (root/"_internal").is_dir() else root
 missing=tuple(v for v in REQUIRED if not (resource_root/v).exists())
 executable=next((p for p in (root/"sus-adb",root/"sus-adb.exe") if p.exists()),None)
 if executable is None:missing+=("sus-adb executable",)
 return {"ok":not missing,"root":root.name,"resource_root":resource_root.name,"missing":missing}
if __name__=="__main__":
 result=verify(sys.argv[1] if len(sys.argv)>1 else "dist/sus-adb-1.0.0-rc.1");print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result["ok"] else 1)
