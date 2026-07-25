"""GUI-neutral addon card and lifecycle projection."""
from app.plugins.plugin_capabilities import HIGH_IMPACT
from app.plugins.plugin_loader import LoaderState
from app.plugins.plugin_ui import AddonCardSpec,AddonCatalogAction,resolve_ui_mode

def lifecycle_for(manager,plugin_id,window_host=None):
    record=manager.records.get(plugin_id);status=manager.loader.statuses.get(plugin_id)
    if record is None:return "Available"
    manifest=record[2]
    trusted=manager.trust.verify(plugin_id,record[1].package_digest)
    if not trusted:return "Permissions Required" if manifest.requested_capabilities else "Trust Required"
    if not set(manifest.requested_capabilities)<=set(manager.trust.approved(plugin_id,record[1].package_digest)):return "Permissions Required"
    if not manifest.enabled:return "Installed"
    if not status or status.state is not LoaderState.ACTIVE:return "Enabled"
    panels=manager.registry.by_plugin(plugin_id);opened=window_host and any(window_host.is_open(c.contribution_id) for c in panels)
    return "Window Open" if opened else "Loaded"

def card_spec(item,manager,window_host=None):
    record=manager.records.get(item.manifest.plugin_id)
    manifest=record[2] if record else item.manifest
    panel=next((c for c in manifest.contributed_components if c.contribution_type=="pentest-panel"),None)
    meta={**manifest.addon_ui,**(panel.metadata if panel else {})}
    actions=tuple(AddonCatalogAction(v["action_id"],v["label"],v["kind"]) for v in meta.get("catalog_actions",()) if isinstance(v,dict) and all(k in v for k in ("action_id","label","kind")))
    update_available=bool(record and item.package_digest!=record[1].package_digest)
    reviewed=bool(update_available and manager.official_update_reviewed(manifest.plugin_id,item.package_digest))
    lifecycle=lifecycle_for(manager,manifest.plugin_id,window_host)
    blocked=lifecycle in {"Loaded","Window Open"}
    update_status=""
    if update_available:
        update_status=f"Update available · Candidate v{item.manifest.version}"
        if item.manifest.version==manifest.version:update_status+="\nPackage contents changed without a version change"
        if reviewed:update_status="Update ready — unload addon before installing" if blocked else "Update reviewed — Install Update is ready"
    return AddonCardSpec(
        manifest.plugin_id,manifest.name,manifest.version,manifest.description,
        len(manifest.requested_capabilities),True,
        bool(set(manifest.requested_capabilities)&HIGH_IMPACT),lifecycle,
        preferred_mode=resolve_ui_mode(meta.get("ui_mode")),
        privacy_note=manifest.caution_text,catalog_actions=actions,
        openable=panel is not None,update_available=update_available,
        update_reviewed=reviewed,update_installable=reviewed and not blocked,
        update_status=update_status,candidate_version=item.manifest.version,
    )

def card_actions(spec):
    lifecycle={
        "Available":("Details","Install"),
        "Trust Required":("Details","Trust"),
        "Permissions Required":("Details","Permissions"),
        "Installed":("Details","Enable"),
        "Enabled":("Details","Load"),
        "Loaded":("Details","Open","Unload"),
        "Window Open":("Details","Focus","Unload"),
        "Error":("Details",),
    }[spec.lifecycle_status]
    if spec.lifecycle_status=="Loaded" and not spec.openable:lifecycle=("Details","Unload")
    values=[lifecycle[0],*(value.label for value in spec.catalog_actions),*lifecycle[1:]]
    if spec.update_available:values.append("Review Update")
    if spec.update_installable:values.append("Install Update")
    return tuple(values)
