"""Plugin lifecycle coordinator; install, trust, enable and load are separate."""
from __future__ import annotations
import json
from dataclasses import dataclass,replace
from pathlib import Path
from app.plugins.plugin_api import PluginAPI
from app.plugins.plugin_capabilities import CAPABILITIES,HIGH_IMPACT
from app.plugins.plugin_loader import PluginLoader,LoaderState
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_validator import PluginValidator
from app.plugins.official_catalog import OfficialPluginCatalog
from app.core.pentest_event import EventCategory,PentestEvent
@dataclass(frozen=True,slots=True)
class ManagerResult:
    ok:bool;manifest:object=None;items:tuple=();status:object=None;path:str|None=None;error:str|None=None;warnings:tuple[str,...]=()
class PluginManager:
    def __init__(self,store,trust,registry,timeline_provider=lambda:None,session_provider=lambda:None,device_provider=lambda:None,target_provider=lambda:None,evidence_provider=lambda:None,finding_provider=lambda:None,app_version="1.0.0",official_root=None,official_tracked_paths=None,auto_refresh=True,host_state=None):
        self.store=store;self.trust=trust;self.registry=registry;self.validator=PluginValidator();self.timeline_provider=timeline_provider;self.session_provider=session_provider;self.device_provider=device_provider;self.target_provider=target_provider;self.evidence_provider=evidence_provider;self.finding_provider=finding_provider;self.app_version=app_version;self.host_state=host_state;self.catalog=OfficialPluginCatalog(official_root,official_tracked_paths) if official_root else None;self.records={};self._listeners=[];self._refreshed=False;self._apis={};self.loader=PluginLoader(registry,self.validator,trust,self._api)
        if auto_refresh:self.refresh()
    def subscribe(self,callback):
        if callback not in self._listeners:self._listeners.append(callback)
        return lambda:self._listeners.remove(callback) if callback in self._listeners else None
    def _changed(self,event="refresh",plugin_id=""):
        for callback in tuple(self._listeners):
            try:callback(event,plugin_id)
            except Exception:continue
    def _api(self,manifest):
        api=self._apis.get(manifest.plugin_id)
        approved=self.trust.approved(manifest.plugin_id,manifest.package_digest)
        if api is not None and api.policy.approved!=frozenset(approved):api.close();api=None
        if api is None:
            api=PluginAPI(manifest.plugin_id,approved,self.session_provider,self.device_provider,self.target_provider,self.timeline_provider,self.evidence_provider,self.finding_provider,self.store.root/"state",host_state=self.host_state,app_version=self.app_version);self._apis[manifest.plugin_id]=api
        return api
    def _release_api(self,plugin_id):
        api=self._apis.pop(plugin_id,None)
        if api is not None:api.close()
    def plugin_context(self,plugin_id):
        record=self.records.get(plugin_id);return self._api(record[2]).context(self.app_version) if record else None
    def subscribe_context(self,plugin_id,callback,replay=True):
        record=self.records.get(plugin_id)
        return self._api(record[2]).subscribe_context(callback,replay=replay) if record else None
    def _event(self,plugin_id,title,description="",severity="info"):
        timeline=self.timeline_provider()
        if timeline:timeline.append(PentestEvent(EventCategory.SESSION,"plugin-manager",title,description,payload={"plugin_id":plugin_id},severity=severity))
    def refresh(self):
        self.records={}
        for path,inspection in self.store.installed():
            state=self.store.state(inspection.manifest.plugin_id);m=replace(inspection.manifest,enabled=bool(state.get("enabled")),trust_state="trusted-local" if self.trust.verify(inspection.manifest.plugin_id,inspection.package_digest) else "untrusted");self.records[m.plugin_id]=(path,inspection,m)
        self._refreshed=True;result=self.list();self._changed();return result
    def ensure_refreshed(self):return self.list() if self._refreshed else self.refresh()
    def inspect(self,source):
        inspection=PluginPackage.inspect(source);validation=self.validator.validate(inspection,existing_ids=self.records)
        return ManagerResult(inspection.ok and validation.valid,inspection.manifest,error="; ".join(validation.errors) or inspection.error,warnings=validation.warnings+validation.capability_cautions)
    def install(self,source):
        inspection=PluginPackage.inspect(source);validation=self.validator.validate(inspection,existing_ids=self.records)
        official=self.catalog.get(inspection.manifest.plugin_id,self.records) if self.catalog and inspection.manifest else None
        if official and Path(source).resolve()!=official.path:return ManagerResult(False,inspection.manifest,error="Official plugin IDs are reserved; change the derivative plugin ID before installation.")
        if validation.errors:return ManagerResult(False,inspection.manifest,error="; ".join(validation.errors),warnings=validation.warnings)
        result=self.store.install(source);self.refresh();self._event(inspection.manifest.plugin_id,"Plugin stored disabled","Installation did not import, enable, trust, or load code.");return ManagerResult(result.ok,inspection.manifest,path=result.path,error=result.error,warnings=validation.warnings)
    def official(self):self.ensure_refreshed();return self.catalog.list(self.records) if self.catalog else ()
    def install_official(self,plugin_id,expected_digest=""):
        item=self.catalog.get(plugin_id,self.records) if self.catalog else None
        if not item:return ManagerResult(False,error="Official plugin was not found in the bundled catalog.")
        if item.installed:return ManagerResult(False,item.manifest,error="Official plugin is already installed.")
        if not item.valid:return ManagerResult(False,item.manifest,error="; ".join(item.errors))
        current=PluginPackage.inspect(item.path)
        if not current.ok or current.package_digest!=item.package_digest or expected_digest and current.package_digest!=expected_digest:return ManagerResult(False,item.manifest,error="Official plugin digest changed before installation.")
        return self.install(item.path)
    def approve(self,plugin_id,capabilities=(),confirmed=False):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        requested=set(record[2].requested_capabilities);approved=set(capabilities)
        if not approved<=requested or not approved<=set(CAPABILITIES):return ManagerResult(False,error="Only requested, known capabilities may be approved.")
        if not requested and not confirmed:return ManagerResult(False,error="Explicit package-digest trust confirmation is required.")
        if approved&HIGH_IMPACT and not confirmed:return ManagerResult(False,error="Explicit high-impact capability confirmation is required.")
        self.trust.approve(plugin_id,record[1].package_digest,tuple(sorted(approved)));self.refresh();self._event(plugin_id,"Plugin trust approved","Approval is bound to the current package digest.");return ManagerResult(True,self.records[plugin_id][2])
    def trust_zero_capability(self,plugin_id,confirmed=False):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        if record[2].requested_capabilities:return ManagerResult(False,error="This addon requests capabilities; review them through Permissions.")
        if not confirmed:return ManagerResult(False,error="Explicit package-digest trust confirmation is required.")
        self.trust.approve(plugin_id,record[1].package_digest,());self.refresh();self._event(plugin_id,"Plugin digest trusted","Zero capabilities approved; enablement and loading remain separate.");return ManagerResult(True,self.records[plugin_id][2])
    def revoke(self,plugin_id):self.unload(plugin_id);self.trust.revoke(plugin_id);self.refresh();return ManagerResult(True)
    def enable(self,plugin_id):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        if not self.trust.verify(plugin_id,record[1].package_digest):return ManagerResult(False,error="Trust approval for this exact digest is required before enabling.")
        if not set(record[2].requested_capabilities)<=set(self.trust.approved(plugin_id,record[1].package_digest)):return ManagerResult(False,error="All requested capabilities must be explicitly approved before enabling.")
        self.store.set_enabled(plugin_id,record[2].version,True,record[1].package_digest);self.refresh();return ManagerResult(True,self.records[plugin_id][2])
    def disable(self,plugin_id):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        self.unload(plugin_id);self.store.set_enabled(plugin_id,record[2].version,False,record[1].package_digest);self.refresh();return ManagerResult(True,self.records[plugin_id][2])
    def load(self,plugin_id):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        if not record[2].enabled:return ManagerResult(False,error="Plugin is disabled; enabling and loading are separate explicit actions.")
        status=self.loader.load(record[0],record[1],enabled=True)
        if status.state is not LoaderState.ACTIVE:self._release_api(plugin_id)
        self._event(plugin_id,"Plugin loaded" if status.state is LoaderState.ACTIVE else "Plugin load failed",status.last_error,severity="error" if status.last_error else "info");return ManagerResult(status.state is LoaderState.ACTIVE,record[2],status=status,error=status.last_error or None)
    def unload(self,plugin_id):
        status=self.loader.unload(plugin_id);self._release_api(plugin_id);self._event(plugin_id,"Plugin unloaded",status.last_error,severity="warning" if status.last_error else "info");self._changed("unload",plugin_id);return ManagerResult(status.state is LoaderState.UNLOADED,status=status,error=status.last_error or None)
    def reload(self,plugin_id):self.unload(plugin_id);return self.load(plugin_id)
    def uninstall(self,plugin_id,confirmed=False):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        self.unload(plugin_id);result=self.store.uninstall(plugin_id,record[2].version,confirmed);self.refresh();self._changed("uninstall",plugin_id);return ManagerResult(result.ok,error=result.error)
    def verify(self,plugin_id):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        current=PluginPackage.inspect(record[0]);expected=self.store.state(plugin_id).get("package_digest",record[1].package_digest);ok=current.ok and current.package_digest==expected
        if not ok:self.trust.revoke(plugin_id,"Package contents changed.");self.store.quarantine(plugin_id,record[2].version,"Digest changed or package invalid.");self.refresh()
        return ManagerResult(ok,record[2],error=None if ok else "Plugin digest changed; trust revoked and package quarantined.")
    def changed_digest_count(self):
        return sum(PluginPackage.inspect(path).package_digest!=self.store.state(m.plugin_id).get("package_digest",inspection.package_digest) for path,inspection,m in self.records.values())
    def quarantine(self,plugin_id,reason="Operator quarantine"):
        record=self.records.get(plugin_id)
        if not record:return ManagerResult(False,error="Plugin was not found.")
        self.unload(plugin_id);self.trust.revoke(plugin_id,reason);r=self.store.quarantine(plugin_id,record[2].version,reason);self.refresh();return ManagerResult(r.ok,error=r.error,path=r.path)
    def list(self,query="",trust="All",enabled=None):
        q=query.casefold();items=[v[2] for v in self.records.values() if (not q or q in (v[2].name+v[2].plugin_id+v[2].description).casefold()) and (trust=="All" or v[2].trust_state.value==trust) and (enabled is None or v[2].enabled==enabled)];return tuple(sorted(items,key=lambda m:m.plugin_id))
    def export_inventory(self,path):
        p=Path(path).resolve();root=self.store.root.resolve()
        if root not in p.parents:raise ValueError("Inventory export must remain inside the plugin store.")
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps([m.to_dict() for m in self.list()],indent=2,sort_keys=True),encoding="utf-8");return str(p)
    def shutdown(self):
        statuses=self.loader.unload_all()
        for plugin_id in tuple(self._apis):self._release_api(plugin_id)
        return statuses
