"""Canonical principal-workspace navigation state.

The controller is intentionally GUI-agnostic.  It gives Home cards, menus,
keyboard shortcuts, and visible workspace controls one route into the shell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


PRINCIPAL_WORKSPACES = (
    "Home",
    "Console",
    "Instrumentation",
    "Scripts",
    "Pentest",
)

WORKSPACE_ALIASES = {
    "home": "Home",
    "workspace home": "Home",
    "console": "Console",
    "instrumentation": "Instrumentation",
    "scripts": "Scripts",
    "script studio": "Scripts",
    "pentest": "Pentest",
}


def normalize_workspace(value: object) -> str:
    """Return a known principal workspace, falling back safely to Home."""

    if not isinstance(value, str):
        return "Home"
    return WORKSPACE_ALIASES.get(value.strip().casefold(), "Home")


def abbreviated_serial(serial: str, limit: int = 18) -> str:
    """Keep a selected serial recognizable without widening the device dock."""

    if len(serial) <= limit:
        return serial
    return f"{serial[:8]}…{serial[-6:]}"


@dataclass(frozen=True, slots=True)
class WorkspaceHomeState:
    """Small immutable state projection used by the lightweight Home view."""

    selected_device: str = ""
    selected_serial: str = ""
    selected_target: str = ""
    active_assessment: str = ""
    selected_script: str = ""
    active_sessions: int = 0
    interface_mode: str = "guided"


class PrincipalWorkspaceController:
    """Own the current principal workspace and invoke one host navigator."""

    def __init__(
        self,
        show_callback: Callable[[str], object],
        *,
        initial: object = "Home",
    ):
        self._show_callback = show_callback
        self.current = normalize_workspace(initial)

    def navigate(self, name: object):
        destination = normalize_workspace(name)
        result = self._show_callback(destination)
        self.current = destination
        return result

    def adopt(self, name: object) -> str:
        """Record navigation performed by the visible workspace selector."""

        self.current = normalize_workspace(name)
        return self.current
