"""Shared, deterministic resolution for externally installed host tools."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path


class HostToolResolver:
    """Resolve configured tools, PATH tools, and active-environment tools once."""

    def __init__(
        self,
        configured: Mapping[str, str] | None = None,
        *,
        which: Callable[[str], str | None] = shutil.which,
        interpreter: str | Path | None = None,
        platform_name: str | None = None,
        packaged: bool | None = None,
        is_file: Callable[[Path], bool] | None = None,
    ):
        self.configured = {str(k): str(v) for k, v in (configured or {}).items() if v}
        self.which = which
        self.interpreter = Path(interpreter or sys.executable)
        self.platform_name = (platform_name or os.name).casefold()
        self.packaged = bool(getattr(sys, "frozen", False)) if packaged is None else packaged
        self.is_file = is_file or Path.is_file
        self._resolved: dict[str, str | None] = {}

    def resolve(self, name: str) -> str | None:
        if name in self._resolved:
            return self._resolved[name]
        configured = self.configured.get(name)
        if configured:
            path = Path(configured).expanduser()
            value = str(path.resolve()) if self.is_file(path) else None
            self._resolved[name] = value
            return value
        found = self.which(name)
        if found:
            value = str(Path(found).resolve())
            self._resolved[name] = value
            return value
        if not self.packaged:
            for executable_name in self.executable_names(name):
                candidate = self.interpreter.parent / executable_name
                if self.is_file(candidate):
                    value = str(candidate.resolve())
                    self._resolved[name] = value
                    return value
        self._resolved[name] = None
        return None

    def record_validated(self, name: str, path: str) -> None:
        """Retain a successfully diagnosed path for all later execution."""
        self._resolved[name] = str(Path(path).resolve())

    def missing_message(self, name: str, display_name: str | None = None) -> str:
        configured = self.configured.get(name)
        label = display_name or name
        if configured:
            return f"Configured {label} executable does not exist: {configured}"
        return (
            f"{label} is unavailable to the GUI process. Configure its executable path "
            "or launch SUS-ADB from the project virtual environment."
        )

    def executable_names(self, name: str) -> tuple[str, ...]:
        if self.platform_name.startswith("win") or self.platform_name == "nt":
            return (name if name.casefold().endswith(".exe") else f"{name}.exe",)
        return (name,)
