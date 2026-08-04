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
    status: str = "missing"


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
                status="missing",
            )

        result = self.runner.run((path, *version_args), timeout=10)
        if result.ok:
            self.resolver.record_validated(name, path)
        version = self._version_text(result) if result.ok else None
        status = "healthy" if result.ok else "timed_out" if result.timed_out else "broken"
        error = None if result.ok else self._health_error(display_name, result)
        return ToolDiagnostic(
            name=name,
            display_name=display_name,
            executable_path=path,
            installed=result.ok,
            version=version,
            error=error,
            command_result=result,
            status=status,
        )

    def diagnose_all(self) -> dict[str, ToolDiagnostic]:
        return {name: self.check(name) for name in self.TOOL_SPECS}

    @staticmethod
    def _version_text(result: CommandResult) -> str | None:
        output = result.stdout or result.stderr
        return output.splitlines()[0].strip() if output.strip() else None

    @staticmethod
    def _health_error(display_name: str, result: CommandResult) -> str:
        if result.timed_out:
            return f"{display_name} health check timed out; verify the selected executable and its environment."
        lines = [line.strip() for line in result.output.splitlines() if line.strip()]
        detail = lines[-1] if lines else f"exit status {result.returncode}"
        if len(detail) > 240:
            detail = detail[:237] + "..."
        return f"{display_name} is present but its health check failed: {detail}"
