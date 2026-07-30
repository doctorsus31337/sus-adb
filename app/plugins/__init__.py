"""Secure local SUS Companion Plugin SDK v1 (stable susadb IDs)."""
PLUGIN_API_VERSION = "1.1"
SUPPORTED_PLUGIN_API_VERSIONS = ("1.0", "1.1")

from app.plugins.plugin_api import PluginAPI,PluginContext,PluginResult
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_interactive import (
    PLUGIN_NAVIGATION_DESTINATIONS,PluginActionClassification,PluginActionRequest,
    PluginActionResult,PluginActionSpec,PluginConfirmationSpec,PluginContextBinding,
    PluginFieldSpec,PluginFieldType,PluginFormSpec,PluginNavigationSpec,
    PluginOptionSpec,PluginProgressUpdate,PluginRefreshBehavior,
)
from app.plugins.plugin_ui import PluginPanelSpec,PluginView

__all__=(
    "PLUGIN_API_VERSION","SUPPORTED_PLUGIN_API_VERSIONS","PLUGIN_NAVIGATION_DESTINATIONS",
    "Contribution","PluginAPI","PluginContext","PluginResult","PluginPanelSpec","PluginView",
    "PluginActionClassification","PluginActionRequest","PluginActionResult",
    "PluginActionSpec","PluginConfirmationSpec","PluginContextBinding",
    "PluginFieldSpec","PluginFieldType","PluginFormSpec","PluginNavigationSpec",
    "PluginOptionSpec","PluginProgressUpdate","PluginRefreshBehavior",
)
