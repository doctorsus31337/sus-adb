"""Preview-first proxy workflows for explicitly selected Android devices."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class ProxyPlan:
    workflow:str; host:str; port:int; commands:tuple[tuple[str,...],...]; guidance:tuple[str,...]
    @property
    def display_text(self):return "\n".join(" ".join(c) for c in self.commands)

class ProxyWorkflowService:
    def __init__(self,diagnostics,proxy_manager):self.diagnostics=diagnostics;self.proxy_manager=proxy_manager
    def readiness(self,host="127.0.0.1",port=8080):return self.diagnostics.diagnose(host,port)
    def build_plan(self,workflow,host,port,device_port=None):
        endpoint=self.proxy_manager.endpoint(host,port);serial=self.proxy_manager.serial
        if not serial:raise ValueError("An explicitly selected device is required.")
        mode=workflow.casefold().replace(" ","-");commands=[]
        if mode in ("physical-device","physical","custom"):
            commands.append(("adb","-s",serial,"shell","settings","put","global","http_proxy",endpoint))
        elif mode in ("emulator",):
            commands.append(("adb","-s",serial,"shell","settings","put","global","http_proxy",endpoint))
        elif mode in ("adb-reverse","reverse"):
            local=f"tcp:{int(device_port or port)}";remote=f"tcp:{int(port)}"
            commands.extend((("adb","-s",serial,"reverse",local,remote),("adb","-s",serial,"shell","settings","put","global","http_proxy",f"127.0.0.1:{int(device_port or port)}")))
        else:raise ValueError("Select Physical Device, Emulator, ADB Reverse, or Custom.")
        guidance=("Review every command before applying.","Proxy configured and proxy reachable are separate states.","Certificate trust is not installed automatically.","TLS pinning may require user-selected Script Studio instrumentation; no bypass is loaded automatically.")
        return ProxyPlan(workflow,str(host),int(port),tuple(commands),guidance)
    def apply(self,plan,confirmed=False):
        if not confirmed:return (False,"Explicit confirmation is required.")
        if plan.workflow.casefold().replace(" ","-") in ("adb-reverse","reverse"):
            mapping=self.proxy_manager.add_mapping("reverse",plan.commands[0][-2],plan.commands[0][-1],True)
            if not mapping.ok:return (False,mapping.error)
            return self.proxy_manager.apply_proxy("127.0.0.1",int(plan.commands[1][-1].rsplit(":",1)[1]),True)
        return self.proxy_manager.apply_proxy(plan.host,plan.port,True)
    def restore_all(self,confirmed=False):return self.proxy_manager.restore_all(confirmed)
    @staticmethod
    def troubleshooting():return {"device-unreachable":"Use a host address reachable from the selected device; 127.0.0.1 means the device itself.","proxy-not-listening":"Start the selected proxy manually and verify only its configured listener.","missing-mapping":"Review explicit adb forward/reverse mappings.","certificate":"Install and trust the proxy CA manually only when authorized.","pinning":"Proxy setup does not bypass TLS pinning. Open Grimoire or Script Studio and review instrumentation explicitly."}
