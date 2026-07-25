"""Threaded, bounded selected-device Logcat collection."""
from __future__ import annotations
import json,re,subprocess,threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from app.core.adb_explorer_models import LogcatEvent
from app.core.adb_package_service import ExplorerResult

class LogcatState(str,Enum):STOPPED="stopped";STARTING="starting";RUNNING="running";PAUSED="paused-display";STOPPING="stopping";FAILED="failed"
class ADBLogcatManager:
    PATTERN=re.compile(r"^(\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+)\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+([^:]+):\s?(.*)$")
    def __init__(self,adb,process_factory=None,callback=lambda e:None,max_lines=5000,evidence_provider=lambda:None):self.adb=adb;self.process_factory=process_factory or self._popen;self.callback=callback;self.buffer=deque(maxlen=max_lines);self.max_lines=max_lines;self.dropped=0;self.state=LogcatState.STOPPED;self.process=None;self.thread=None;self.serial="";self.target="";self.paused=False
    @staticmethod
    def _popen(argv):return subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
    @classmethod
    def parse(cls,line,serial="",target=""):
        m=cls.PATTERN.match(line.rstrip())
        return LogcatEvent(m.group(1),int(m.group(2)),int(m.group(3)),m.group(4),m.group(5).strip(),m.group(6),line.rstrip(),serial,target) if m else None
    def start(self,serial,target=""):
        if not serial:return ExplorerResult(False,error="No device is selected.")
        self.stop();self.serial,self.target=serial,target;argv=(self.adb.adb_path or "adb","-s",serial,"logcat","-v","threadtime");self.state=LogcatState.STARTING
        try:self.process=self.process_factory(argv);self.state=LogcatState.RUNNING;self.thread=threading.Thread(target=self._read,daemon=True);self.thread.start();return ExplorerResult(True,preview=argv)
        except Exception as exc:self.state=LogcatState.FAILED;return ExplorerResult(False,error=f"Unable to start Logcat: {exc}",preview=argv)
    def _read(self):
        try:
            for line in self.process.stdout:
                event=self.parse(line,self.serial,self.target)
                if not event:continue
                if len(self.buffer)==self.max_lines:self.dropped+=1
                self.buffer.append(event)
                if not self.paused:
                    try:self.callback(event)
                    except Exception:pass
        finally:
            if self.state not in {LogcatState.STOPPING,LogcatState.STOPPED}:self.state=LogcatState.STOPPED
    def stop(self):
        if self.process:
            self.state=LogcatState.STOPPING
            try:self.process.terminate();self.process.wait(timeout=2)
            except Exception:
                try:self.process.kill()
                except Exception:pass
        self.process=None;self.state=LogcatState.STOPPED
    def pause_display(self,paused=True):self.paused=paused;self.state=LogcatState.PAUSED if paused else LogcatState.RUNNING
    def clear_display(self):self.buffer.clear();self.dropped=0
    def clear_device(self,confirmed=False):return ExplorerResult(False,error="Explicit confirmation is required.") if not confirmed else self._run_clear()
    def _run_clear(self):
        r=self.adb.run("logcat","-c",serial=self.serial);return ExplorerResult(r.ok,result=r,error=r.output if not r.ok else None)
    def filtered(self,pid=None,priorities=(),tags=(),search=""):
        q=search.casefold();pt=set(priorities);tg={t.casefold() for t in tags};return tuple(e for e in self.buffer if (pid is None or e.pid==int(pid)) and (not pt or e.priority in pt) and (not tg or e.tag.casefold() in tg) and q in (e.tag+e.message).casefold())
    def export_text(self,events=None):return "\n".join(e.raw_line for e in (events or self.buffer))
    def export_jsonl(self,events=None):return "\n".join(json.dumps(e.to_dict(),sort_keys=True) for e in (events or self.buffer))
