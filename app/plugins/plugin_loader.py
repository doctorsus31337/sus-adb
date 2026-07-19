"""Explicit trusted-plugin loader with failure containment."""
from __future__ import annotations
import importlib.util,sys
from dataclasses import dataclass
from enum import Enum
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_package import PluginPackage
class LoaderState(str,Enum): DISCOVERED="discovered";VALIDATED="validated";DISABLED="disabled";LOADING="loading";ACTIVE="active";FAILED="failed";UNLOADING="unloading";UNLOADED="unloaded";BLOCKED="blocked"
@dataclass(frozen=True,slots=True)
class LoaderStatus:
    plugin_id:str;state:LoaderState;last_error:str=""
class PluginLoader:
    def __init__(self,registry,validator,trust_store,api_factory):self.registry=registry;self.validator=validator;self.trust=trust_store;self.api_factory=api_factory;self.statuses={};self.instances={};self.modules={}
    def load(self,path,inspection=None,enabled=False):
        inspection=inspection or PluginPackage.inspect(path);m=inspection.manifest if inspection.ok else None
        if not m:return self._status("unknown",LoaderState.FAILED,inspection.error or "Inspection failed.")
        if not enabled:return self._status(m.plugin_id,LoaderState.DISABLED,"Plugin loading requires a separate explicit enable action.")
        self.statuses[m.plugin_id]=LoaderStatus(m.plugin_id,LoaderState.LOADING)
        current=PluginPackage.inspect(path)
        if not current.ok or current.package_digest!=inspection.package_digest:return self._status(m.plugin_id,LoaderState.BLOCKED,"Package digest changed before loading.")
        if not self.trust.verify(m.plugin_id,current.package_digest):return self._status(m.plugin_id,LoaderState.BLOCKED,"Plugin is not trusted for this exact package digest.")
        validation=self.validator.validate(current,root=path)
        if not validation.valid:return self._status(m.plugin_id,LoaderState.BLOCKED,"; ".join(validation.errors))
        try:
            rel,class_name=(m.entry_point.split(":",1)+["Plugin"])[:2];module_path=(__import__('pathlib').Path(path)/rel.replace(".","/")).with_suffix(".py") if not rel.endswith(".py") else __import__('pathlib').Path(path)/rel
            module_name=f"sus_adb_plugin_{m.plugin_id.replace('-','_')}";spec=importlib.util.spec_from_file_location(module_name,module_path)
            if not spec or not spec.loader:raise ImportError("Could not create isolated plugin module specification.")
            module=importlib.util.module_from_spec(spec);sys.modules[module_name]=module;old_bytecode=sys.dont_write_bytecode;sys.dont_write_bytecode=True
            try:spec.loader.exec_module(module)
            finally:sys.dont_write_bytecode=old_bytecode
            plugin_class=getattr(module,class_name);instance=plugin_class();api=self.api_factory(m)
            raw=instance.activate(api)
            contributions=tuple(v if isinstance(v,Contribution) else Contribution(plugin_id=m.plugin_id,**v) for v in (raw or ()))
            self.registry.register(m.plugin_id,contributions);self.instances[m.plugin_id]=instance;self.modules[m.plugin_id]=module_name;return self._status(m.plugin_id,LoaderState.ACTIVE)
        except Exception as exc:
            self.registry.unregister_plugin(m.plugin_id);self.instances.pop(m.plugin_id,None);name=self.modules.pop(m.plugin_id,None) or f"sus_adb_plugin_{m.plugin_id.replace('-','_')}";sys.modules.pop(name,None);return self._status(m.plugin_id,LoaderState.FAILED,str(exc))
    def unload(self,plugin_id):
        instance=self.instances.get(plugin_id)
        try:
            if instance and hasattr(instance,"deactivate"):instance.deactivate()
        except Exception as exc:error=str(exc)
        else:error=""
        self.registry.unregister_plugin(plugin_id);self.instances.pop(plugin_id,None);name=self.modules.pop(plugin_id,None)
        if name:sys.modules.pop(name,None)
        return self._status(plugin_id,LoaderState.FAILED if error else LoaderState.UNLOADED,error)
    def unload_all(self):return tuple(self.unload(i) for i in tuple(self.instances))
    def _status(self,plugin_id,state,error=""):status=LoaderStatus(plugin_id,state,error);self.statuses[plugin_id]=status;return status
