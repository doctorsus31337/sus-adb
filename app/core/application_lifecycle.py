"""Ordered startup and bounded best-effort shutdown coordination."""
from __future__ import annotations
import time,threading
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class LifecycleResult:
    ok:bool;completed:tuple[str,...]=();errors:tuple[str,...]=();duration:float=0
class ApplicationLifecycle:
    STARTUP_ORDER=("metadata","configuration","logging","recovery","theme","core-managers","gui","diagnostics","plugins","device-discovery")
    def __init__(self,shutdown_timeout=5):self.shutdown_timeout=shutdown_timeout;self.cleanups=[]
    def startup(self,steps):
        done=[];errors=[];started=time.monotonic()
        for name in self.STARTUP_ORDER:
            fn=steps.get(name)
            if fn:
                try:fn();done.append(name)
                except Exception as exc:errors.append(f"{name}: {exc}")
        return LifecycleResult(not errors,tuple(done),tuple(errors),time.monotonic()-started)
    def add_cleanup(self,name,callback):self.cleanups.append((name,callback))
    def shutdown(self):
        done=[];errors=[];started=time.monotonic();deadline=started+self.shutdown_timeout
        for name,fn in reversed(self.cleanups):
            if time.monotonic()>=deadline:errors.append("Shutdown timeout reached.");break
            failure=[]
            def invoke():
                try:fn()
                except Exception as exc:failure.append(exc)
            worker=threading.Thread(target=invoke,name=f"sus-adb-shutdown-{name}",daemon=True);worker.start();worker.join(max(0,deadline-time.monotonic()))
            if worker.is_alive():errors.append(f"{name}: cleanup timed out.");break
            if failure:errors.append(f"{name}: {failure[0]}")
            else:done.append(name)
        return LifecycleResult(not errors,tuple(done),tuple(errors),time.monotonic()-started)
