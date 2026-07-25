"""Injected optional APK tool diagnostics; never installs tools."""
from __future__ import annotations
import os,shutil
from app.core.apk_lab_models import ApkToolRecord
class ApkToolDiagnostics:
 TOOLS={"adb":("version",),"aapt":("version",),"aapt2":("version",),"apkanalyzer":("--version",),"apktool":("--version",),"jadx":("--version",),"jadx-gui":("--version",),"apksigner":("version",),"zipalign":("-h",),"keytool":("-help",),"bundletool":("version",),"java":("-version",)}
 def __init__(self,runner,lookup=shutil.which,overrides=None):self.runner=runner;self.lookup=lookup;self.overrides=dict(overrides or {})
 def diagnose(self):
  items=[]
  for name,args in self.TOOLS.items():
   configured=self.overrides.get(name,"");path=configured if configured and os.path.isfile(configured) else self.lookup(name) or "";version=""
   if path:
    r=self.runner.run((path,*args),timeout=8);version=((r.stdout or r.stderr).splitlines() or [""])[0]
   items.append(ApkToolRecord(name,path,bool(path),version,"No installation or download was attempted.",configured))
  return tuple(items)
