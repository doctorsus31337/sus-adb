"""Injected, shell-free process adapter for bounded packet capture."""
from __future__ import annotations
from dataclasses import dataclass
import subprocess

@dataclass(frozen=True,slots=True)
class CaptureProcessState:
    running:bool=False;returncode:int|None=None;stdout:str="";stderr:str="";error:str|None=None

class PacketCaptureProcess:
    def __init__(self,popen_factory=subprocess.Popen):self.popen_factory=popen_factory;self.process=None;self.argv=()
    def start(self,argv):
        if self.process and self.process.poll() is None:return CaptureProcessState(True,error="A capture process is already running.")
        try:
            self.argv=tuple(str(x) for x in argv);self.process=self.popen_factory(self.argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,shell=False)
            return CaptureProcessState(True)
        except (OSError,ValueError) as exc:return CaptureProcessState(error=str(exc))
    def state(self):
        if not self.process:return CaptureProcessState()
        code=self.process.poll();return CaptureProcessState(code is None,code)
    def stop(self,timeout=3):
        if not self.process:return CaptureProcessState()
        try:
            if self.process.poll() is None:self.process.terminate()
            out,err=self.process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill();out,err=self.process.communicate()
        return CaptureProcessState(False,self.process.returncode,out or "",err or "")
    def cancel(self,timeout=1):return self.stop(timeout)
