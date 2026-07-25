from __future__ import annotations
import hashlib,json,shutil
from pathlib import Path
class FridaGadgetInstrumentation:
 def plan(self,artifact,architectures,gadget,architecture,config,session=None):
  p=Path(gadget).resolve()
  if not p.is_file():return (False,"Explicit user-supplied Gadget file is required.")
  if architecture not in architectures:return (False,"Gadget architecture is incompatible.")
  if not session or not session.permits("apk-analysis") or not (session.permits("instrumentation-resilience-testing") or session.permits("state-changing-testing")):return (False,"Active APK and instrumentation/state-changing scope is required.")
  return (True,{"classification":"Instrumented Test Build","gadget":str(p),"architecture":architecture,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"config":dict(config),"changes":(f"lib/{architecture}/libfrida-gadget.so","lib/{architecture}/libfrida-gadget.config.so")})
 def apply(self,plan,derived,confirmed=False):
  if not confirmed:return (False,"Explicit confirmation is required.")
  root=Path(derived).resolve()
  if root.exists():return (False,"Derived workspace exists.")
  lib=root/"lib"/plan["architecture"];lib.mkdir(parents=True);shutil.copy2(plan["gadget"],lib/"libfrida-gadget.so");(lib/"libfrida-gadget.config.so").write_text(json.dumps(plan["config"],indent=2,sort_keys=True),encoding="utf-8");(root/"gadget-changes.json").write_text(json.dumps(plan,indent=2,sort_keys=True),encoding="utf-8");return (True,str(root))
