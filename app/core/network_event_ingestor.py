"""Additive normalization and storage of structured network runtime events."""
from __future__ import annotations
import json
from collections import deque
from app.core.network_models import NetworkEvent,NetworkEventType
from app.core.pentest_event import EventCategory,PentestEvent

class NetworkEventIngestor:
    TYPES={e.value for e in NetworkEventType}
    def __init__(self,runtime,max_events=1000,timeline_provider=lambda:None,evidence_provider=lambda:None,session_provider=lambda:None):
        self.runtime=runtime;self.events=deque(maxlen=max(1,max_events));self.dropped=0;self.paused=False;self.listeners=[];self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.session_provider=session_provider;runtime.add_event_listener(self.ingest)
    def add_listener(self,listener):
        if listener not in self.listeners:self.listeners.append(listener)
    def ingest(self,event):
        raw=getattr(event,"payload",event);payload=raw.get("payload",raw) if isinstance(raw,dict) else None
        if not isinstance(payload,dict):return None
        channel=payload.get("channel") or payload.get("source")
        kind=str(payload.get("event_type") or payload.get("type") or "").casefold()
        if channel not in ("sus-adb-network","network") or kind not in self.TYPES:return None
        try:
            item=NetworkEvent(kind,source=str(payload.get("source_name") or getattr(event,"script_id","") or "runtime"),script_id=payload.get("script_id") or getattr(event,"script_id",None),process_id=payload.get("process_id"),thread_id=payload.get("thread_id"),protocol=str(payload.get("protocol", "")),direction=str(payload.get("direction", "")),host=str(payload.get("host", "")),port=int(payload["port"]) if payload.get("port") not in (None,"") else None,method=str(payload.get("method", "")),url=str(payload.get("url", "")),status_code=int(payload["status_code"]) if payload.get("status_code") not in (None,"") else None,headers=payload.get("headers") or {},body_preview=str(payload.get("body_preview", ""))[:4096],body_size=int(payload.get("body_size") or 0),binary_summary=str(payload.get("binary_summary", "")),device_serial=str(payload.get("device_serial", "")),target_identifier=str(payload.get("target_identifier", "")),severity=str(payload.get("severity","info")),payload=payload)
        except (TypeError,ValueError):return None
        if len(self.events)==self.events.maxlen:self.dropped+=1
        self.events.append(item)
        if not self.paused:
            for listener in tuple(self.listeners):listener(item)
        return item
    def filter(self,event_type="",host="",port=None,method="",status_code=None,script="",search=""):
        q=search.casefold();return tuple(e for e in self.events if (not event_type or e.event_type.value==event_type) and (not host or host.casefold() in e.host.casefold()) and (port in (None,"") or e.port==int(port)) and (not method or e.method.casefold()==method.casefold()) and (status_code in (None,"") or e.status_code==int(status_code)) and (not script or script.casefold() in (e.script_id or "").casefold()) and (not q or q in (e.display_text+json.dumps(e.to_dict(),sort_keys=True)).casefold()))
    def export_jsonl(self,path,events=None):
        chosen=tuple(events) if events is not None else tuple(self.events)
        with open(path,"w",encoding="utf-8") as stream:
            for event in chosen:stream.write(json.dumps(event.to_dict(),sort_keys=True,default=str)+"\n")
        return path
    def add_to_evidence(self,events):
        events=tuple(events)
        session=self.session_provider();store=self.evidence_provider()
        if not session or not session.permits("evidence-collection"):return (False,"Evidence-collection scope is required.")
        if not store:return (False,"No active evidence store.")
        text="\n".join(json.dumps(e.to_dict(),sort_keys=True,default=str) for e in events);result=store.add_text("Structured network events",text,description="Authorized runtime network metadata")
        timeline=self.timeline_provider()
        if result.ok and timeline:timeline.append(PentestEvent(EventCategory.EVIDENCE,"network-workspace","Network events added to evidence",f"{len(events)} event(s)"))
        return (result.ok,result.item if result.ok else result.error)
    def close(self):self.runtime.remove_event_listener(self.ingest);self.listeners.clear()
