"""Public-SDK declaration for the host-owned Logcat Investigator workspace."""

from app.plugins import Contribution, PluginPanelSpec, PluginView


def panel_spec(_context=None):
    """Honest static fallback when the specialized host workspace is unavailable."""
    return PluginPanelSpec(
        "Logcat Investigator",
        (
            PluginView(
                "Host Workspace Unavailable",
                "Live capture requires the SUS Companion host-owned Logcat "
                "workspace and approved read-selected-device plus "
                "read-device-logs capabilities. This fallback does not display "
                "logs, imitate capture, or start any device operation.",
                warning=(
                    "Device logs may contain identifiers, paths, messages, "
                    "tokens, account information, and application data."
                ),
            ),
        ),
        {
            "Capture": "Not started",
            "Host workspace": "Unavailable",
        },
    )


class Plugin:
    def __init__(self):
        self.api = None

    def activate(self, api):
        self.api = api
        return (
            Contribution(
                "logcat-investigator.panel",
                "pentest-panel",
                "Logcat Investigator",
                factory=panel_spec,
                metadata={
                    "ui_mode": "window",
                    "singleton": True,
                    "device_selector": True,
                    "workspace_kind": "logcat-investigator",
                    "default_width": 1180,
                    "default_height": 780,
                    "minimum_width": 900,
                    "minimum_height": 650,
                },
            ),
        )

    def deactivate(self):
        self.api = None
