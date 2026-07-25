"""Runtime Explorer orchestration over the existing shared Frida runtime."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from app.core.evidence_item import EvidenceType
from app.core.pentest_event import EventCategory, PentestEvent
from app.core.runtime_explorer_models import RuntimeEvent, RuntimeEventType, RuntimeHookSpec


@dataclass(frozen=True, slots=True)
class ExplorerResult:
    ok: bool
    value: Any = None
    error: str | None = None
    warning: str | None = None


@dataclass(slots=True)
class ActiveRuntimeHook:
    spec: RuntimeHookSpec
    descriptor: Any
    loaded_at: str
    event_count: int = 0
    last_error: str | None = None


class RuntimeExplorerService:
    def __init__(self, discovery, builder, library, runtime, session_provider=lambda:None, timeline_provider=lambda:None, evidence_provider=lambda:None, open_script_callback: Callable[[Any], None] | None = None, max_events=2000):
        self.discovery=discovery;self.builder=builder;self.library=library;self.runtime=runtime;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.open_script_callback=open_script_callback
        self.serial="";self.target=None;self.preview=None;self.preview_spec=None;self.saved_descriptor=None;self.active={};self.listeners=[];self.events=[];self.max_events=max(10,int(max_events));self.dropped=0
        if hasattr(runtime,"add_event_listener"):runtime.add_event_listener(self._runtime_event)

    def select(self,serial,target):
        old=(self.serial,self._target_id());new=(serial or "",getattr(target,"identifier",None) or getattr(target,"name","") if target else "")
        if old!=new:
            self.unload_all();self.preview=self.preview_spec=self.saved_descriptor=None;self.discovery.mark_stale("Selected device or target changed")
        self.serial,self.target=new[0],target;self.discovery.select(self.serial,target)

    def _target_id(self):return getattr(self.target,"identifier",None) or getattr(self.target,"name","") if self.target else ""
    def readiness(self):return self.discovery.readiness()
    def add_listener(self,listener):
        if listener not in self.listeners:self.listeners.append(listener)
    def remove_listener(self,listener):
        if listener in self.listeners:self.listeners.remove(listener)

    def generate(self,spec):
        if spec.selected_target!=self._target_id():return ExplorerResult(False,error="The hook specification does not match the selected target.")
        result=self.builder.build(spec)
        if not result.ok:self._timeline("Hook generation failed",result.error or "",EventCategory.ERROR);return ExplorerResult(False,error=result.error)
        self.preview=result;self.preview_spec=spec;self.saved_descriptor=None;self._timeline("Runtime hook generated",spec.display_label);return ExplorerResult(True,result)

    def save_preview(self):
        if not self.preview or not self.preview_spec:return ExplorerResult(False,error="Generate and review a script preview first.")
        root=Path(self.library.root);script_path=root/"frida"/"generated"/self.preview.filename;metadata_path=root/"metadata"/f"{Path(self.preview.filename).stem}.meta.json"
        try:
            script_path.parent.mkdir(parents=True,exist_ok=True);metadata_path.parent.mkdir(parents=True,exist_ok=True)
            if script_path.exists():
                if script_path.read_text(encoding="utf-8")!=self.preview.source:return ExplorerResult(False,error="A different generated script already uses this filename.")
                scanned=self.library.scan();found=next((item for item in scanned.descriptors if Path(item.path)==script_path),None) if scanned.ok else None
                self.saved_descriptor=found or self._absolute_descriptor(script_path,metadata_path);return ExplorerResult(True,self.saved_descriptor,warning="Identical generated script already exists.")
            script_path.write_text(self.preview.source,encoding="utf-8")
            portable=self.preview.descriptor.to_dict();portable["path"]=f"frida/generated/{self.preview.filename}";portable["metadata_path"]=f"metadata/{metadata_path.name}"
            metadata_path.write_text(json.dumps(portable,indent=2,sort_keys=True,default=str),encoding="utf-8")
            scanned=self.library.scan()
            if not scanned.ok:return ExplorerResult(False,error=scanned.error)
            self.saved_descriptor=next((item for item in scanned.descriptors if Path(item.path)==script_path),None)
            if not self.saved_descriptor:return ExplorerResult(False,error="Generated script could not be indexed by Script Studio.")
            self._timeline("Runtime hook saved",self.preview_spec.display_label);return ExplorerResult(True,self.saved_descriptor)
        except (OSError,TypeError,ValueError) as exc:return ExplorerResult(False,error=f"Could not save generated script: {exc}")

    def _absolute_descriptor(self,script_path,metadata_path):
        from dataclasses import replace
        return replace(self.preview.descriptor,path=str(script_path),metadata_path=str(metadata_path))

    def open_in_script_studio(self):
        if not self.saved_descriptor:return ExplorerResult(False,error="Save the generated script before opening it in Script Studio.")
        if self.open_script_callback:self.open_script_callback(self.saved_descriptor)
        return ExplorerResult(True,self.saved_descriptor)

    def load_preview(self,confirmed=False):
        if not confirmed:return ExplorerResult(False,error="Explicit confirmation is required immediately before loading the visible hook.")
        if not self.saved_descriptor:return ExplorerResult(False,error="Save the reviewed generated script before loading it.")
        spec=self.preview_spec
        if not self.serial or not self.target:return ExplorerResult(False,error="An explicitly selected device and target are required.")
        if spec.changes_runtime:
            session=self.session_provider()
            if not session or not session.permits("state-changing-testing"):return ExplorerResult(False,error="An active authorized scope permitting state-changing-testing is required.")
            scope=session.scope
            if scope.device_serial!=self.serial or (scope.package_identifier or scope.target_name)!=self._target_id():return ExplorerResult(False,error="The selected device and target do not match the active authorized scope.")
        loaded=self.runtime.load_script(self.saved_descriptor,confirm_untrusted=True,confirm_state_change=spec.changes_runtime)
        if not loaded.ok:self._timeline("Runtime hook load failed",loaded.error or "",EventCategory.ERROR);return ExplorerResult(False,error=loaded.error)
        self.active[spec.hook_id]=ActiveRuntimeHook(spec,self.saved_descriptor,loaded.value.loaded_at);self._timeline("Runtime hook loaded",spec.display_label,EventCategory.HIGH_IMPACT_ACTION if spec.changes_runtime else EventCategory.SCRIPT);return ExplorerResult(True,self.active[spec.hook_id],warning=loaded.warning)

    def unload(self,hook_id):
        hook=self.active.get(hook_id)
        if not hook:return ExplorerResult(True,warning="The Runtime Explorer hook is not active.")
        result=self.runtime.unload_script(hook.descriptor.script_id)
        if result.ok:self.active.pop(hook_id,None);self._timeline("Runtime hook unloaded",hook.spec.display_label);return ExplorerResult(True)
        hook.last_error=result.error;return ExplorerResult(False,error=result.error)

    def unload_all(self):return tuple(self.unload(hook_id) for hook_id in tuple(self.active))
    def list_active(self):return tuple(self.active.values())

    def _runtime_event(self,event):
        payload=getattr(event,"payload",{}) or {};sent=payload.get("payload",{}) if isinstance(payload,dict) else {}
        if not isinstance(sent,dict) or sent.get("channel")!="sus-adb-runtime":return
        hook_id=str(sent.get("hookId",""));body=sent.get("payload",{}) if isinstance(sent.get("payload",{}),dict) else {}
        try:kind=RuntimeEventType(sent.get("eventType","warning"))
        except ValueError:kind=RuntimeEventType.WARNING
        runtime_event=RuntimeEvent(kind,hook_id,str(sent.get("owner","")),str(sent.get("member","")),arguments=tuple(body.get("arguments",())),return_value=body.get("returnValue"),exception=body.get("exception"),stack_trace=str(body.get("stack","")),payload=body,raw_message=payload,severity="error" if kind in {RuntimeEventType.ERROR,RuntimeEventType.EXCEPTION} else "info",device_serial=self.serial,target_identifier=self._target_id())
        hook=self.active.get(hook_id)
        if hook:hook.event_count+=1;hook.last_error=str(runtime_event.exception) if runtime_event.exception else hook.last_error
        self._accept_event(runtime_event)

    def _accept_event(self,event):
        self.events.append(event)
        if len(self.events)>self.max_events:self.events.pop(0);self.dropped+=1
        for listener in tuple(self.listeners):
            try:listener(event)
            except Exception:pass

    def export_jsonl(self,path,events: Iterable[RuntimeEvent] | None=None):
        try:Path(path).write_text("\n".join(json.dumps(item.to_dict(),sort_keys=True,default=str) for item in (events or self.events)),encoding="utf-8");return ExplorerResult(True,str(path))
        except OSError as exc:return ExplorerResult(False,error=str(exc))

    def add_evidence(self,events):
        selected=tuple(events);session=self.session_provider();store=self.evidence_provider()
        if not session or not session.permits("evidence-collection") or not store:return ExplorerResult(False,error="An active case permitting evidence-collection is required.")
        text="\n".join(json.dumps(item.to_dict(),sort_keys=True,default=str) for item in selected)
        result=store.add_text("Runtime Explorer events",text,EvidenceType.RUNTIME_OBSERVATION,device_serial=self.serial,target_identifier=self._target_id(),related_event_ids=tuple(item.event_id for item in selected),tags=("runtime-explorer",))
        if result.ok:self._timeline("Runtime evidence added",f"{len(selected)} event(s)",EventCategory.EVIDENCE);return ExplorerResult(True,result.item)
        return ExplorerResult(False,error=result.error)

    def _timeline(self,title,description,category=EventCategory.SCRIPT):
        timeline=self.timeline_provider()
        if timeline:timeline.append(PentestEvent(category,"runtime-explorer",title,description,related_target_identifier=self._target_id()))

    def cleanup(self):
        results=self.unload_all()
        if hasattr(self.runtime,"remove_event_listener"):self.runtime.remove_event_listener(self._runtime_event)
        return results
