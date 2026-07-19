"""Minimal local-only performance measurements; no telemetry."""
from __future__ import annotations
import time,threading
from dataclasses import dataclass,field
@dataclass(frozen=True,slots=True)
class PerformanceSnapshot:
    durations:dict=field(default_factory=dict);memory_bytes:int|None=None;event_buffer_sizes:dict=field(default_factory=dict);active_workers:int=0;warnings:tuple[str,...]=()
class PerformanceMonitor:
    def __init__(self,enabled=False,thresholds=None,clock=time.monotonic):self.enabled=enabled;self.thresholds=dict(thresholds or {});self.clock=clock;self.starts={};self.durations={}
    def start(self,name):
        if self.enabled:self.starts[name]=self.clock()
    def stop(self,name):
        if self.enabled and name in self.starts:self.durations[name]=self.clock()-self.starts.pop(name)
        return self.durations.get(name,0)
    def record(self,name,duration):
        if self.enabled:self.durations[str(name)]=max(0.0,float(duration))
    def snapshot(self,event_buffers=None):
        warnings=tuple(f"{k} exceeded local threshold {self.thresholds[k]:g}s" for k,v in self.durations.items() if k in self.thresholds and v>self.thresholds[k]);return PerformanceSnapshot(dict(self.durations),event_buffer_sizes=dict(event_buffers or {}),active_workers=sum(t.is_alive() for t in threading.enumerate())-1,warnings=warnings)
