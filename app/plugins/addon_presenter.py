"""GUI-neutral addon card and lifecycle projection."""
from app.plugins.plugin_capabilities import HIGH_IMPACT
from app.plugins.plugin_ui import AddonCardSpec,resolve_ui_mode

def lifecycle_for(manager,plugin_id,window_host=None):
    record=manager.records.get(plugin_id);status=manager.loader.statuses.get(plugin_id)
    if record is None:return "Available"
    manifest=record[2]
    if not manager.trust.verify(plugin_id,record[1].package_digest):return "Permissions Required"
    if not manifest.enabled:return "Installed"
    if not status or status.state.value!="active":return "Enabled"
    panels=manager.registry.by_plugin(plugin_id);opened=window_host and any(window_host.is_open(c.contribution_id) for c in panels)
    return "Window Open" if opened else "Loaded"

def card_spec(item,manager,window_host=None):
    manifest=item.manifest;panel=next((c for c in manifest.contributed_components if c.contribution_type=="pentest-panel"),None);meta=panel.metadata if panel else manifest.addon_ui
    return AddonCardSpec(manifest.plugin_id,manifest.name,manifest.version,manifest.description,len(manifest.requested_capabilities),True,bool(set(manifest.requested_capabilities)&HIGH_IMPACT),lifecycle_for(manager,manifest.plugin_id,window_host),preferred_mode=resolve_ui_mode(meta.get("ui_mode")),privacy_note=manifest.caution_text)
