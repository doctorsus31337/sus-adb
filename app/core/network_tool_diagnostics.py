"""Optional host network-tool diagnostics without starting tools."""
from __future__ import annotations
import os,shutil
from dataclasses import dataclass
from pathlib import Path
from app.core.network_models import HostProxyTool

@dataclass(frozen=True,slots=True)
class ToolDiagnosticResult:
 ok:bool;tools:tuple[HostProxyTool,...]=();error:str|None=None

class NetworkToolDiagnostics:
 COMMANDS={"mitmproxy":("--version",),"mitmweb":("--version",),"mitmdump":("--version",),"tcpdump":("--version",),"tshark":("--version",),"wireshark":("--version",)}
 def __init__(self,runner,lookup=shutil.which,port_probe=None,burp_path=""):
  self.runner=runner;self.lookup=lookup;self.port_probe=port_probe;self.burp_path=burp_path
 def diagnose(self,host="127.0.0.1",port=8080):
  try:
   port=int(port)
   if not host.strip() or not 1<=port<=65535:return ToolDiagnosticResult(False,error="An explicit host and valid port are required.")
   listening=bool(self.port_probe(host,port)) if self.port_probe else False;items=[]
   for name,args in self.COMMANDS.items():
    path=self.lookup(name) or "";version=""
    if path:
     result=self.runner.run((path,*args),timeout=5);version=(result.stdout or result.stderr).splitlines()[0] if result.ok and (result.stdout or result.stderr) else ""
    items.append(HostProxyTool(name,path,bool(path),version,listening if name.startswith("mitm") else False,host,port,"Tool was not started; readiness is diagnostic only."))
   path=str(Path(self.burp_path).expanduser()) if self.burp_path else "";installed=bool(path and os.path.isfile(path));items.append(HostProxyTool("Burp Suite",path,installed,"",listening,host,port,"Configure the Burp launcher path when automatic discovery is unavailable."))
   return ToolDiagnosticResult(True,tuple(items))
  except Exception as exc:return ToolDiagnosticResult(False,error=f"Host tool diagnostics failed: {exc}")
