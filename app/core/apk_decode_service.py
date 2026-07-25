from __future__ import annotations
import shutil,zipfile
from pathlib import Path
class ApkDecodeService:
 def __init__(self,runner=None):self.runner=runner;self.cancelled=False;self.active=False
 def preview(self,tool,source,output):return ((tool,"d","-f",str(source),"-o",str(output)) if "apktool" in tool else (tool,"-d",str(output),str(source)))
 def extract(self,source,output,confirmed=False):
  if not confirmed:return (False,"Explicit execution is required.")
  out=Path(output).resolve()
  if out.exists():return (False,"Output exists; overwrite is forbidden.")
  self.active=True
  try:
   with zipfile.ZipFile(source) as z:
    for i in z.infolist():
     target=(out/i.filename).resolve()
     if out not in target.parents:raise ValueError("Archive traversal rejected.")
    z.extractall(out)
   return (True,str(out))
  except Exception as exc:shutil.rmtree(out,ignore_errors=True);return (False,str(exc))
  finally:self.active=False
 def cancel(self):self.cancelled=True;self.active=False
 def cleanup(self):self.cancel()
