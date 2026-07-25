"""Structured host-tool diagnostics for SUS-ADB."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.command_result import CommandResult
from app.core.command_runner import CommandRunner
from app.core.host_tool_resolver import HostToolResolver


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
        which=None,
        resolver: HostToolResolver | None = None,
        configured: dict[str, str] | None = None,
    ):
        self.runner = runner or CommandRunner()
        self.resolver = resolver or HostToolResolver(configured, **({"which": which} if which else {}))

    def check(self, name: str) -> ToolDiagnostic:
        if name not in self.TOOL_SPECS:
            raise ValueError(f"Unsupported tool: {name}")
        display_name, version_args = self.TOOL_SPECS[name]
        path = self.resolver.resolve(name)
        if not path:
            result = CommandResult.from_command(
                (name, *version_args), -1,
                error=self.resolver.missing_message(name, display_name),
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
        if result.ok:
            self.resolver.record_validated(name, path)
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
