"""Selected-session Runtime Explorer discovery with local bounded caches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core import runtime_agent_templates as templates
from app.core.runtime_explorer_models import JavaClassRecord, JavaFieldRecord, JavaMethodRecord, NativeModuleRecord, NativeSymbolRecord, RuntimeEvent, RuntimeEventType


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    ok: bool
    value: Any = None
    error: str | None = None
    warning: str | None = None


class RuntimeDiscoveryService:
    def __init__(self, runtime, event_callback: Callable[[RuntimeEvent], None] | None = None, max_results: int = 5000, timeout: float = 15.0):
        self.runtime = runtime; self.adapter = runtime.adapter; self.event_callback = event_callback
        self.max_results = max(1, int(max_results)); self.timeout = max(0.1, float(timeout)); self.serial = ""; self.target = None
        self.java_available: bool | None = None; self.classes = (); self.methods = {}; self.fields = {}; self.modules = (); self.exports = {}; self.stale = True

    def select(self, serial, target):
        identity = getattr(target, "identifier", None) or getattr(target, "name", "")
        if serial != self.serial or identity != self._target_id(): self.clear_caches()
        self.serial, self.target = serial or "", target

    def _target_id(self): return getattr(self.target, "identifier", None) or getattr(self.target, "name", "") if self.target else ""
    def clear_caches(self): self.classes=(); self.methods={}; self.fields={}; self.modules=(); self.exports={}; self.java_available=None; self.stale=True
    def mark_stale(self, reason="Selection changed"):
        self.clear_caches(); self._emit(RuntimeEventType.LIFECYCLE, {"message": reason})

    def _emit(self, kind, payload, severity="info"):
        if self.event_callback:
            try:self.event_callback(RuntimeEvent(kind, payload=payload, severity=severity, device_serial=self.serial, target_identifier=self._target_id()))
            except Exception:pass

    def _guard(self, cancellation=None):
        if not self.serial or self.target is None: return DiscoveryResult(False, error="Select a device and target before runtime discovery.")
        if cancellation is not None and cancellation.is_set(): return DiscoveryResult(False, error="Runtime discovery was cancelled.")
        if self.runtime.session is None: return DiscoveryResult(False, error="Attach or spawn the explicitly selected target in Script Studio first.")
        runtime_target = getattr(self.runtime.target, "identifier", None) or getattr(self.runtime.target, "name", "")
        if runtime_target != self._target_id() or self.runtime.serial != self.serial: return DiscoveryResult(False, error="The active Frida session does not match the selected device and target.")
        return None

    def _request(self, source, cancellation=None):
        guarded = self._guard(cancellation)
        if guarded: return guarded
        script = None; messages=[]
        try:
            created=self.adapter.create_script(self.runtime.session,source)
            if not created.ok:return DiscoveryResult(False,error=created.error)
            script=created.value
            registered=self.adapter.register_message_callback(script,lambda message,data=None:messages.append((message,data)))
            if not registered.ok:return DiscoveryResult(False,error=registered.error)
            loaded=self.adapter.load_script(script)
            if not loaded.ok:return DiscoveryResult(False,error=loaded.error)
            if cancellation is not None and cancellation.is_set():return DiscoveryResult(False,error="Runtime discovery was cancelled.")
            called=self.adapter.call_export(script,"enumerate" if "enumerate:function" in source else "readiness")
            if not called.ok:return DiscoveryResult(False,error=called.error)
            value=called.value if isinstance(called.value,dict) else {}
            if value.get("error"):return DiscoveryResult(False,value=tuple(value.get("items",())),error=str(value["error"]))
            return DiscoveryResult(True,value)
        except Exception as exc:
            return DiscoveryResult(False,error=f"Runtime discovery failed: {exc}")
        finally:
            if script is not None:self.adapter.unload_script(script)

    def readiness(self, cancellation=None):
        base=self.runtime.readiness(self.serial,self.target)
        if not base.ok:return DiscoveryResult(False,error=base.error,warning=base.warning)
        result=self._request(templates.readiness_probe(),cancellation)
        if result.ok:self.java_available=bool(result.value.get("javaAvailable"));self.stale=False
        return result

    def enumerate_java_classes(self,cancellation=None):
        result=self._request(templates.java_class_enumeration(),cancellation)
        if not result.ok:return result
        self.java_available=True; items=result.value.get("items",()); target=self._target_id()
        self.classes=tuple(JavaClassRecord(str(item.get("className","")),loader_description=str(item.get("loaderDescription","")),classification=str(item.get("classification","class")),device_serial=self.serial,target_identifier=target) for item in items if isinstance(item,dict) and item.get("className"))[:self.max_results];self.stale=False;self._emit(RuntimeEventType.DISCOVERY,{"kind":"java-classes","count":len(self.classes)});return DiscoveryResult(True,self.classes)

    def search_java_classes(self,query="",namespace="",limit=None):
        q=query.casefold().strip();ns=namespace.casefold().strip();maximum=min(self.max_results,limit or self.max_results)
        return tuple(item for item in self.classes if (not q or q in item.class_name.casefold()) and (not ns or item.namespace.casefold().startswith(ns)))[:maximum]

    def enumerate_java_methods(self,class_name,cancellation=None):
        result=self._request(templates.java_member_enumeration(class_name),cancellation)
        if not result.ok:return result
        target=self._target_id(); records=[]
        for item in result.value.get("items",()):
            if not isinstance(item,dict) or not item.get("methodName"):continue
            records.append(JavaMethodRecord(class_name,str(item["methodName"]),int(item.get("overloadIndex",0)),tuple(map(str,item.get("argumentTypes",()))),str(item.get("returnType","void")),bool(item.get("isStatic")),item.get("methodName")=="$init",bool(item.get("isNative")),str(item.get("visibility","")),self.serial,target))
        self.methods[class_name]=tuple(records)[:self.max_results];return DiscoveryResult(True,self.methods[class_name])

    def enumerate_java_fields(self,class_name,cancellation=None):
        result=self._request(templates.java_member_enumeration(class_name,True),cancellation)
        if not result.ok:return result
        target=self._target_id();self.fields[class_name]=tuple(JavaFieldRecord(class_name,str(item.get("fieldName")),str(item.get("typeName","")),bool(item.get("isStatic")),str(item.get("visibility","")),item.get("valuePreview"),self.serial,target) for item in result.value.get("items",()) if isinstance(item,dict) and item.get("fieldName"))[:self.max_results];return DiscoveryResult(True,self.fields[class_name])

    def enumerate_native_modules(self,cancellation=None):
        result=self._request(templates.native_module_enumeration(),cancellation)
        if not result.ok:return result
        target=self._target_id();self.modules=tuple(NativeModuleRecord(str(item.get("moduleName")),str(item.get("path","")),str(item.get("baseAddress","")),int(item.get("size",0)),self.serial,target) for item in result.value.get("items",()) if isinstance(item,dict) and item.get("moduleName"))[:self.max_results];self.stale=False;return DiscoveryResult(True,self.modules)

    def search_modules(self,query="",limit=None):
        q=query.casefold().strip();return tuple(item for item in self.modules if not q or q in (item.module_name+item.path).casefold())[:limit or self.max_results]

    def enumerate_native_exports(self,module_name,cancellation=None):
        result=self._request(templates.native_export_enumeration(module_name),cancellation)
        if not result.ok:return result
        target=self._target_id();self.exports[module_name]=tuple(NativeSymbolRecord(str(item.get("symbolName")),str(item.get("symbolType","export")),str(item.get("address","")),module_name,self.serial,target) for item in result.value.get("items",()) if isinstance(item,dict) and item.get("symbolName"))[:self.max_results];return DiscoveryResult(True,self.exports[module_name])

    def search_exports(self,module_name,query="",limit=None):
        q=query.casefold().strip();return tuple(item for item in self.exports.get(module_name,()) if not q or q in item.symbol_name.casefold())[:limit or self.max_results]
