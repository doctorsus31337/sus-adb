"""Read-only, injected host/environment diagnostics."""
from __future__ import annotations
import importlib.util,platform,shutil,sys
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True,slots=True)
class DiagnosticRecord:
    name:str;available:bool;required:bool=False;version:str="";path:str="";guidance:str=""
class EnvironmentDiagnostics:
    TOOLS=("adb","fastboot","frida","frida-ps","objection","java","apktool","jadx","apksigner","zipalign","keytool","bundletool","tcpdump","tshark","wireshark","mitmproxy","mitmweb","mitmdump","x-terminal-emulator","gnome-terminal","konsole","xterm")
    def __init__(self,lookup=shutil.which,version_runner=None,module_finder=importlib.util.find_spec):self.lookup=lookup;self.version_runner=version_runner;self.module_finder=module_finder
    def run(self,config_dir=None,workspace_dir=None):
        records=[DiagnosticRecord("Python",sys.version_info>=(3,11),True,platform.python_version(),sys.executable,"Python 3.11+ is required."),DiagnosticRecord("CustomTkinter",bool(self.module_finder("customtkinter")),True,guidance="Install the pinned runtime requirements."),DiagnosticRecord("Frida Python",bool(self.module_finder("frida")),False,guidance="Optional; required only for Frida runtime workflows.")]
        for tool in self.TOOLS:
            path=self.lookup(tool);version=""
            if path and self.version_runner:
                try:version=str(self.version_runner((path,"--version")))[:200]
                except Exception:version="Version unavailable"
            records.append(DiagnosticRecord(tool,bool(path),tool=="adb",version,path or "",f"Install/configure {tool} only if its workflow is needed."))
        for name,path in (("Configuration directory",config_dir),("Workspace directory",workspace_dir)):
            if path:
                try:p=Path(path);p.mkdir(parents=True,exist_ok=True);ok=p.is_dir()
                except OSError:ok=False
                records.append(DiagnosticRecord(name,ok,True,path=str(path),guidance="Choose a user-writable local directory."))
        records.append(DiagnosticRecord("Platform",True,True,f"{platform.system()} {platform.machine()}"));return tuple(records)
