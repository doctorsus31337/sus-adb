"""Heavily commented zero-capability learning template.

Copy this package, choose a new stable plugin ID, and update the semantic version.
Plugins import public ``app.plugins`` SDK models only. They never receive raw Tk,
unrestricted subprocess or filesystem access, secret providers, or raw managers.
All commented examples remain opt-in TODOs and register nothing by default.
"""
from __future__ import annotations
from dataclasses import dataclass
from app.plugins.plugin_api import PluginResult
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_interactive import (
    PluginActionResult,PluginActionSpec,PluginFieldSpec,PluginFieldType,
    PluginFormSpec,PluginNavigationSpec,PluginOptionSpec,PluginRefreshBehavior,
)
from app.plugins.plugin_ui import PluginPanelSpec,PluginView

@dataclass(frozen=True,slots=True)
class LocalState:
    """TODO: immutable plugin-local state; persist only through an approved façade."""
    message:str="inactive"

def demonstrate(request):
    """Runs only after an explicit click; performs no operational work."""
    name=request.values["display_name"]
    return PluginActionResult(
        True,f"Validated {name}. No external action was performed.",
        (("Refresh","Host-owned immutable panel replacement"),),
        panel_spec(message=f"Last explicit demonstration: {name}"),
    )

def open_help(_request):
    return PluginActionResult(
        True,"Opening host-owned contextual help.",
        navigation=PluginNavigationSpec("contextual-help"),
    )

def panel_spec(_context=None,message="No action has run."):
    form=PluginFormSpec("skeleton.demo",(
        PluginFieldSpec("display_name","Display name",required=True,default="Derivative example",max_length=80,validation_hint="Choose a short educational label."),
        PluginFieldSpec("presentation","Presentation",PluginFieldType.CHOICE,default="guided",options=(PluginOptionSpec("guided","Guided"),PluginOptionSpec("advanced","Advanced"))),
        PluginFieldSpec("notes","Notes",PluginFieldType.MULTILINE,max_length=400,placeholder="Runtime-only notes"),
    ),"Inert informational form","The host validates these runtime-only values before invoking the callback.")
    actions=(
        PluginActionSpec("skeleton.demonstrate","Validate and Refresh",demonstrate,"Explicit no-op demonstration; opening the panel never invokes it.",form=form,refresh=PluginRefreshBehavior.PANEL,primary=True),
        PluginActionSpec("skeleton.help","Open Contextual Help",open_help,"Safe host-owned navigation only."),
    )
    # Capability-gated derivative examples may declare read-selected-device or
    # read-selected-target and bind an action to that immutable context. Never
    # invent capabilities or call ADB/process/network/filesystem APIs directly.
    return PluginPanelSpec("Skeleton Module",(PluginView("Documentation","Plugin API 1.1 educational template. The host owns fields, actions, navigation, workers, theme, and cleanup."),),{"Capabilities":"0","Behavior":"Explicit only","Result":message},actions)

class Plugin:
    def __init__(self):
        # Constructor: allocate no worker, device, network, process, GUI, or file resource.
        self.api=None;self.state=LocalState()
    def validate(self):
        # Return a structured result; do not probe services during static validation.
        return PluginResult(True,self.state)
    def load(self,api):self.api=api;return PluginResult(True)
    def register(self):
        # TODO examples: dashboard-card, pentest-panel, menu-action, script-asset,
        # diagnostic-provider, evidence-processor, finding-template, report-section,
        # parser, and assessment-action. Register stable owned IDs only after opt-in.
        return (Contribution("skeleton.documentation","pentest-panel","Skeleton Module Documentation",factory=panel_spec,metadata={"ui_mode":"window","singleton":True}),)
    def start(self):
        # TODO: use a bounded cancellable worker; marshal GUI results through host callbacks.
        # Read selected-device/target context and active scope through capability-gated API only.
        # Timeline, evidence, and finding creation each require explicit approved capabilities.
        return PluginResult(True)
    def stop(self):return PluginResult(True)
    def unregister(self):return PluginResult(True)
    def unload(self):self.api=None;return PluginResult(True)
    def activate(self,api):
        # Host lifecycle entry point. Validation/load/register/start are intentionally no-op.
        self.load(api);return self.register()
    def deactivate(self):
        # Cancel workers, release owned resources, unregister, and forget façade references.
        self.stop();self.unregister();self.unload()
