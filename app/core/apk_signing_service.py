from __future__ import annotations
from pathlib import Path
class ApkSigningService:
 def __init__(self,runner,secret_provider):self.runner=runner;self.secret_provider=secret_provider;self.active=False
 def preview(self,tool,apk,keystore,alias):return (tool,"sign","--ks",str(keystore),"--ks-key-alias",alias,"--ks-pass","pass:<redacted>",str(apk))
 def sign(self,tool,apk,output,keystore,alias,confirmed=False):
  if not confirmed:return (False,"Explicit signing confirmation is required.")
  if not Path(keystore).is_file() or not alias:return (False,"Explicit keystore and alias are required.")
  password=self.secret_provider();argv=(tool,"sign","--ks",str(keystore),"--ks-key-alias",alias,"--ks-pass","stdin","--out",str(output),str(apk));r=self.runner.run(argv,timeout=120);password=None;return (bool(r.ok and Path(output).exists()),str(output) if r.ok else r.output)
 def cleanup(self):self.active=False
