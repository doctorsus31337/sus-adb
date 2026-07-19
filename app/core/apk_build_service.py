from __future__ import annotations
from pathlib import Path
class ApkBuildService:
 def __init__(self,runner):self.runner=runner;self.active=False;self.cancelled=False
 def preview_build(self,tool,source,output):return (tool,"b",str(source),"-o",str(output))
 def preview_align(self,tool,source,output):return (tool,"-f","4",str(source),str(output))
 def execute(self,argv,output,confirmed=False):
  if not confirmed:return (False,"Explicit stage confirmation is required.")
  if Path(output).exists():return (False,"Output exists; overwrite forbidden.")
  self.active=True;r=self.runner.run(tuple(argv),timeout=300);self.active=False
  return (bool(r.ok and Path(output).exists()),r.output if not r.ok else str(output))
 def cancel(self):self.cancelled=True;self.active=False
 def cleanup(self):self.cancel()
