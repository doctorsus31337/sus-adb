"""Portable resolution of packaged SUS Companion branding assets."""

from __future__ import annotations

import sys
from pathlib import Path


RUNTIME_DIRECTORY = Path("assets/branding/runtime")
APP_ICON_PNG = "sus-companion-icon-256.png"
APP_ICON_ICO = "sus-companion.ico"
HEADER_ARTWORK = "sus-companion-header.png"
ABOUT_ARTWORK = "sus-companion-about.png"


def application_resource_root() -> Path:
    """Return the source or PyInstaller resource root without using cwd."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parents[2]


class BrandingAssetResolver:
    def __init__(self, resource_root=None):
        self.resource_root = Path(
            resource_root if resource_root is not None else application_resource_root()
        )

    def resolve(self, filename: str) -> Path | None:
        if Path(filename).name != filename:
            return None
        candidate = self.resource_root / RUNTIME_DIRECTORY / filename
        return candidate if candidate.is_file() else None
