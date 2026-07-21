"""Heavily commented zero-capability learning template.

Copy this package, choose a new stable plugin ID, and update the semantic version.
Plugins import public ``app.plugins`` SDK models only. They never receive raw Tk,
unrestricted subprocess or filesystem access, secret providers, or raw managers.
All commented examples remain opt-in TODOs and register nothing by default.
"""
from __future__ import annotations
from dataclasses import dataclass
from app.plugins.plugin_api import PluginResult

@dataclass(frozen=True,slots=True)
class LocalState:
    """TODO: immutable plugin-local state; persist only through an approved façade."""
    message:str="inactive"

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
        return ()
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
