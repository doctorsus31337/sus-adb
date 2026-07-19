"""Structured host-tool diagnostics for SUS-ADB."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from collections.abc import Callable

from app.core.command_result import CommandResult
from app.core.command_runner import CommandRunner


@dataclass(frozen=True, slots=True)
class ToolDiagnostic:
    name: str
    display_name: str
    executable_path: str | None
    installed: bool
    version: str | None = None
    error: str | None = None
    command_result: CommandResult | None = None


class ToolDiagnostics:
    """Checks known host tools without raising when they are unavailable."""

    TOOL_SPECS = {
        "adb": ("ADB", ("version",)),
        "fastboot": ("Fastboot", ("--version",)),
        "frida": ("Frida", ("--version",)),
        "frida-ps": ("frida-ps", ("--version",)),
        "objection": ("Objection", ("version",)),
    }

    def __init__(
        self,
        runner: CommandRunner | None = None,
        which: Callable[[str], str | None] | None = None,
    ):
        self.runner = runner or CommandRunner()
        self.which = which or shutil.which

    def check(self, name: str) -> ToolDiagnostic:
        if name not in self.TOOL_SPECS:
            raise ValueError(f"Unsupported tool: {name}")
        display_name, version_args = self.TOOL_SPECS[name]
        path = self.which(name)
        if not path:
            result = CommandResult.from_command(
                (name, *version_args), -1, error=f"{display_name} was not found in PATH."
            )
            return ToolDiagnostic(
                name=name,
                display_name=display_name,
                executable_path=None,
                installed=False,
                error=result.error,
                command_result=result,
            )

        result = self.runner.run((path, *version_args), timeout=10)
        version = self._version_text(result) if result.ok else None
        return ToolDiagnostic(
            name=name,
            display_name=display_name,
            executable_path=path,
            installed=True,
            version=version,
            error=None if result.ok else (result.output or "Version check failed."),
            command_result=result,
        )

    def diagnose_all(self) -> dict[str, ToolDiagnostic]:
        return {name: self.check(name) for name in self.TOOL_SPECS}

    @staticmethod
    def _version_text(result: CommandResult) -> str | None:
        output = result.stdout or result.stderr
        return output.splitlines()[0].strip() if output.strip() else None
