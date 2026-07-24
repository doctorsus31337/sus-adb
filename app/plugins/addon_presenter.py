"""GUI-neutral addon card and lifecycle projection."""
from app.plugins.plugin_capabilities import HIGH_IMPACT
from app.plugins.plugin_ui import AddonCardSpec,AddonCatalogAction,resolve_ui_mode

def lifecycle_for(manager,plugin_id,window_host=None):
    record=manager.records.get(plugin_id);status=manager.loader.statuses.get(plugin_id)
    if record is None:return "Available"
    bundled=manager.catalog.get(plugin_id,manager.records) if manager.catalog else None
    if bundled and bundled.package_digest!=record[1].package_digest:return "Update Available"
    manifest=record[2]
    trusted=manager.trust.verify(plugin_id,record[1].package_digest)
    if not trusted:return "Permissions Required" if manifest.requested_capabilities else "Trust Required"
    if not set(manifest.requested_capabilities)<=set(manager.trust.approved(plugin_id,record[1].package_digest)):return "Permissions Required"
    if not manifest.enabled:return "Installed"
    if not status or status.state.value!="active":return "Enabled"
    panels=manager.registry.by_plugin(plugin_id);opened=window_host and any(window_host.is_open(c.contribution_id) for c in panels)
    return "Window Open" if opened else "Loaded"

def card_spec(item,manager,window_host=None):
    manifest=item.manifest;panel=next((c for c in manifest.contributed_components if c.contribution_type=="pentest-panel"),None);meta={**manifest.addon_ui,**(panel.metadata if panel else {})}
    actions=tuple(AddonCatalogAction(v["action_id"],v["label"],v["kind"]) for v in meta.get("catalog_actions",()) if isinstance(v,dict) and all(k in v for k in ("action_id","label","kind")))
    return AddonCardSpec(manifest.plugin_id,manifest.name,manifest.version,manifest.description,len(manifest.requested_capabilities),True,bool(set(manifest.requested_capabilities)&HIGH_IMPACT),lifecycle_for(manager,manifest.plugin_id,window_host),preferred_mode=resolve_ui_mode(meta.get("ui_mode")),privacy_note=manifest.caution_text,catalog_actions=actions,openable=panel is not None)

def card_actions(spec):
    lifecycle={"Available":("Details","Install"),"Update Available":("Details","Review Update"),"Trust Required":("Details","Trust"),"Permissions Required":("Details","Permissions"),"Installed":("Details","Enable"),"Enabled":("Details","Load"),"Loaded":("Details","Open","Unload"),"Window Open":("Details","Focus","Unload"),"Error":("Details",)}[spec.lifecycle_status]
    if spec.lifecycle_status=="Loaded" and not spec.openable:lifecycle=("Details","Unload")
    return (lifecycle[0],)+tuple(v.label for v in spec.catalog_actions)+lifecycle[1:]
