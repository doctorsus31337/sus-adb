from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,UnidentifiedImageError
REQUIRED=("VERSION","build-info.json","app/themes","app/resources/startup_tips.json","docs","plugins/examples","packaging/curated-script-assets.json")
BRANDING_REQUIRED=(
 "assets/branding/runtime/manifest.json",
 "assets/branding/runtime/sus-companion-icon-1024.png",
 "assets/branding/runtime/sus-companion-icon-256.png",
 "assets/branding/runtime/sus-companion-icon-16.png",
 "assets/branding/runtime/sus-companion.ico",
 "assets/branding/runtime/sus-companion-header.png",
 "assets/branding/runtime/sus-companion-about.png",
)
EXCLUDED=("flutter_popup_bypass.js","flutter_popup_bypass.meta.json")
EXAMPLE_ASSETS=("plugins/examples/hello_plugin/assets/hello_observer.js","plugins/examples/hello_plugin/assets/hello_observer.meta.json")
BLOCKED_PARTS=("__pycache__",".pytest_cache")
OFFICIAL_IDS=("susadb.device-rescue-recovery","susadb.rootability-advisor","susadb.webview-security-inspector","susadb.skeleton-module","susadb.frida-tutorial","susadb.objection-tutorial")
OFFICIAL_CAPABILITIES={
 "susadb.device-rescue-recovery":("read-selected-device","run-adb-readonly","access-active-case","append-timeline","create-evidence","contribute-report-section"),
 "susadb.rootability-advisor":("read-selected-device","read-selected-target","run-adb-readonly","access-active-case","append-timeline","create-findings","contribute-report-section"),
 "susadb.webview-security-inspector":("read-selected-target","access-frida-runtime","load-frida-script","access-active-case","append-timeline","create-findings","contribute-report-section"),
 "susadb.skeleton-module":(),
 "susadb.frida-tutorial":("read-selected-device","read-selected-target"),
 "susadb.objection-tutorial":("read-selected-device","read-selected-target"),
}
def frida_runtime_errors(resource_root,platform_name):
 metadata=tuple(resource_root.glob("frida-*.dist-info/METADATA"))
 suffix=".pyd" if platform_name=="windows" else ".so"
 native=tuple((resource_root/"frida").glob(f"_frida*{suffix}"))
 errors=[]
 if not metadata:errors.append("frida distribution metadata")
 if not native:errors.append(f"frida native runtime (*{suffix})")
 return tuple(errors)
def pillow_runtime_errors(resource_root):
 metadata=tuple(resource_root.glob("pillow-*.dist-info/METADATA"))
 return () if metadata else ("Pillow distribution metadata",)
def verify(root):
 root=Path(root);resource_root=root/"_internal" if (root/"_internal").is_dir() else root
 missing=tuple(v for v in REQUIRED if not (resource_root/v).exists())
 preferred=next((p for p in (root/"sus-companion",root/"sus-companion.exe") if p.exists()),None)
 legacy=next((p for p in (root/"sus-adb",root/"sus-adb.exe",root/"sus-adb.cmd") if p.exists()),None)
 if preferred is None:missing+=("sus-companion executable",)
 if legacy is None:missing+=("sus-adb compatibility launcher",)
 if not any(part in root.name for part in ("linux","windows")):missing+=("platform-qualified package name",)
 platform_name="windows" if "windows" in root.name.casefold() or (root/"sus-companion.exe").exists() else "linux"
 missing+=frida_runtime_errors(resource_root,platform_name)
 missing+=pillow_runtime_errors(resource_root)
 missing+=tuple(path for path in BRANDING_REQUIRED if not (resource_root/path).is_file())
 if platform_name=="linux":
  if not (root/"sus-companion.png").is_file():missing+=("sus-companion.png",)
  if not (resource_root/"packaging/linux/sus-adb.desktop").is_file():missing+=("packaging/linux/sus-adb.desktop",)
 unexpected=list(name for name in EXCLUDED if any(p.name==name for p in root.rglob("*")))
 unexpected.extend(p.relative_to(root).as_posix() for p in root.rglob("*") if any(part in BLOCKED_PARTS for part in p.relative_to(root).parts) or (p.is_file() and p.suffix.casefold() in {".pyc",".pyo"}))
 example_missing=tuple(path for path in EXAMPLE_ASSETS if not (resource_root/path).is_file())
 missing+=example_missing
 asset_errors=[];core_counts={};core_total=0;build_info={}
 try:
  expected_png_sizes={
   "sus-companion-icon-1024.png":(1024,1024),
   "sus-companion-icon-256.png":(256,256),
   "sus-companion-icon-16.png":(16,16),
   "sus-companion-header.png":(256,256),
   "sus-companion-about.png":(392,584),
  }
  branding_root=resource_root/"assets/branding/runtime"
  for filename,size in expected_png_sizes.items():
   with Image.open(branding_root/filename) as image:
    if image.format!="PNG" or image.size!=size or image.getexif():asset_errors.append(f"branding:{filename}")
  with Image.open(branding_root/"sus-companion.ico") as image:
   expected={(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)}
   if image.format!="ICO" or set(image.info.get("sizes",()))!=expected:asset_errors.append("branding:sus-companion.ico")
  if platform_name=="linux":
   with Image.open(root/"sus-companion.png") as image:
    if image.format!="PNG" or image.size!=(256,256):asset_errors.append("branding:linux-launcher")
   if "Icon=sus-companion" not in (resource_root/"packaging/linux/sus-adb.desktop").read_text(encoding="utf-8"):asset_errors.append("branding:linux-desktop")
 except (OSError,ValueError,KeyError,TypeError,UnidentifiedImageError):asset_errors.append("branding-runtime")
 try:
  build_info=json.loads((resource_root/"build-info.json").read_text(encoding="utf-8"))
  build_keys=("product","version","commit","short_commit","ref","timestamp","channel")
  if any(not isinstance(build_info.get(key),str) or not build_info[key].strip() for key in build_keys):asset_errors.append("build-info-fields")
  if build_info.get("product")!="SUS Companion":asset_errors.append("build-info-product")
  if build_info.get("short_commit")!=(build_info.get("commit","")[:12] or "unknown"):asset_errors.append("build-info-commit")
  if build_info.get("version")!=(resource_root/"VERSION").read_text(encoding="utf-8").strip():asset_errors.append("build-info-version")
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):asset_errors.append("build-info.json")
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
  expected_build={key:build_info.get(key) for key in ("version","commit","short_commit","ref","timestamp","channel")}
  if manifest.get("build")!=expected_build:integrity.append("build-metadata")
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
 return {"ok":not missing and not unexpected and not integrity and not asset_errors,"root":root.name,"resource_root":resource_root.name,"build":build_info,"missing":missing,"excluded_present":tuple(unexpected),"integrity_errors":tuple(integrity),"asset_errors":tuple(asset_errors),"assets":assets}
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("root",nargs="?",default="dist/sus-companion-1.0.0-rc.2-linux-x86_64");parser.add_argument("--output");args=parser.parse_args();result=verify(args.root);report=json.dumps(result,indent=2,sort_keys=True)+"\n"
 if args.output:Path(args.output).write_text(report,encoding="utf-8")
 print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result["ok"] else 1)
