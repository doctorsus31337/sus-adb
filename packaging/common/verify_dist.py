from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
REQUIRED=("VERSION","app/themes","docs","plugins/examples","packaging/curated-script-assets.json")
EXCLUDED=("flutter_popup_bypass.js","flutter_popup_bypass.meta.json")
EXAMPLE_ASSETS=("plugins/examples/hello_plugin/assets/hello_observer.js","plugins/examples/hello_plugin/assets/hello_observer.meta.json")
BLOCKED_PARTS=("__pycache__",".pytest_cache")
OFFICIAL_IDS=("susadb.device-rescue-recovery","susadb.rootability-advisor","susadb.webview-security-inspector","susadb.skeleton-module")
OFFICIAL_CAPABILITIES={
 "susadb.device-rescue-recovery":("read-selected-device","run-adb-readonly","access-active-case","append-timeline","create-evidence","contribute-report-section"),
 "susadb.rootability-advisor":("read-selected-device","run-adb-readonly","access-active-case","append-timeline","create-findings","contribute-report-section"),
 "susadb.webview-security-inspector":("read-selected-target","access-frida-runtime","load-frida-script","access-active-case","append-timeline","create-findings","contribute-report-section"),
 "susadb.skeleton-module":(),
}
def frida_runtime_errors(resource_root,platform_name):
 metadata=tuple(resource_root.glob("frida-*.dist-info/METADATA"))
 suffix=".pyd" if platform_name=="windows" else ".so"
 native=tuple((resource_root/"frida").glob(f"_frida*{suffix}"))
 errors=[]
 if not metadata:errors.append("frida distribution metadata")
 if not native:errors.append(f"frida native runtime (*{suffix})")
 return tuple(errors)
def verify(root):
 root=Path(root);resource_root=root/"_internal" if (root/"_internal").is_dir() else root
 missing=tuple(v for v in REQUIRED if not (resource_root/v).exists())
 executable=next((p for p in (root/"sus-adb",root/"sus-adb.exe") if p.exists()),None)
 if executable is None:missing+=("sus-adb executable",)
 if not any(part in root.name for part in ("linux","windows")):missing+=("platform-qualified package name",)
 platform_name="windows" if "windows" in root.name.casefold() or (root/"sus-adb.exe").exists() else "linux"
 missing+=frida_runtime_errors(resource_root,platform_name)
 unexpected=list(name for name in EXCLUDED if any(p.name==name for p in root.rglob("*")))
 unexpected.extend(p.relative_to(root).as_posix() for p in root.rglob("*") if any(part in BLOCKED_PARTS for part in p.relative_to(root).parts) or (p.is_file() and p.suffix.casefold() in {".pyc",".pyo"}))
 example_missing=tuple(path for path in EXAMPLE_ASSETS if not (resource_root/path).is_file())
 missing+=example_missing
 asset_errors=[];core_counts={};core_total=0
 try:
  asset_report=json.loads((resource_root/"packaging/curated-script-assets.json").read_text(encoding="utf-8"))
  core=asset_report["core_curated_script_studio_assets"];categories=core["categories"]
  for category in ("frida","metadata","objection","profiles"):
   details=categories[category];paths=tuple(details["paths"]);core_counts[category]=details["count"]
   if details["count"]!=len(paths):asset_errors.append(f"count:{category}")
   for path in paths:
    candidate=Path(path)
    if candidate.is_absolute() or ".." in candidate.parts or not (resource_root/candidate).is_file():asset_errors.append(f"asset:{path}")
  core_total=sum(core_counts.values())
  if core["count"]!=core_total:asset_errors.append("count:total")
  local=asset_report["user_local_script_studio_assets"]
  if local!={"count":0,"packaged":False}:asset_errors.append("user-local-assets")
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):asset_errors.append("curated-script-assets.json")
 try:
  plugin=json.loads((resource_root/"plugins/examples/hello_plugin/manifest.json").read_text(encoding="utf-8"))
  if plugin.get("enabled",False) is not False:asset_errors.append("hello-plugin-enabled")
 except (OSError,ValueError,TypeError,json.JSONDecodeError):asset_errors.append("hello-plugin-manifest")
 official={}
 for directory in sorted((resource_root/"plugins/official").glob("*")):
  if not directory.is_dir():continue
  try:
   data=json.loads((directory/"manifest.json").read_text(encoding="utf-8"));plugin_id=data["plugin_id"]
   files=tuple((p.relative_to(directory).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size) for p in sorted(directory.rglob("*")) if p.is_file())
   digest=hashlib.sha256(json.dumps(files,separators=(",",":"),sort_keys=True).encode()).hexdigest();official[plugin_id]={"digest":digest,"capabilities":tuple(data.get("requested_capabilities",())),"enabled":data.get("enabled",False)}
   if data.get("enabled",False) is not False:asset_errors.append(f"official-enabled:{plugin_id}")
   if tuple(data.get("requested_capabilities",()))!=OFFICIAL_CAPABILITIES.get(plugin_id):asset_errors.append(f"official-capabilities:{plugin_id}")
  except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):asset_errors.append(f"official-manifest:{directory.name}")
 for plugin_id in OFFICIAL_IDS:
  if plugin_id not in official:missing+=(f"official plugin: {plugin_id}",)
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
 assets={"core_curated_script_studio_assets":{"count":core_total,"categories":core_counts},"example_plugin_assets":{"count":sum((resource_root/path).is_file() for path in EXAMPLE_ASSETS)},"official_bundled_plugins":{"count":len(official),"plugins":official},"installed_third_party_plugins":{"count":0,"packaged":False},"user_created_local_plugins":{"count":0,"packaged":False},"user_local_script_studio_assets":{"count":0,"packaged":False}}
 return {"ok":not missing and not unexpected and not integrity and not asset_errors,"root":root.name,"resource_root":resource_root.name,"missing":missing,"excluded_present":tuple(unexpected),"integrity_errors":tuple(integrity),"asset_errors":tuple(asset_errors),"assets":assets}
if __name__=="__main__":
 result=verify(sys.argv[1] if len(sys.argv)>1 else "dist/sus-adb-1.0.0-rc.1-linux-x86_64");print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result["ok"] else 1)
