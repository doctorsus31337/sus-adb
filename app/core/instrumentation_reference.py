"""Immutable Frida and Objection command reference definitions."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Mapping

from app.core.frida_session_manager import FridaSessionManager
from app.core.frida_target import FridaTarget


FRIDA_REPL_STARTER = (
    "Process.id",
    "Process.arch",
    "Process.platform",
    "Java.available",
    "Java.androidVersion",
)

OBJECTION_REPL_STARTER = (
    "help",
    "env",
    "ls",
    "android hooking list activities",
    "android hooking list classes",
)


@dataclass(frozen=True, slots=True)
class ReferenceCommand:
    tool: str
    category: str
    command: str
    description: str
    explanation: str
    execution_context: str
    changes_runtime: bool = False
    requires_target: bool = False
    requires_pid: bool = False
    requires_identifier: bool = False
    caution: str | None = None

    @property
    def classification(self) -> str:
        return "Changes Runtime" if self.changes_runtime else "Read-only"

    @property
    def display_label(self) -> str:
        return f"{self.tool} · {self.category} · {self.command}"

    @property
    def search_text(self) -> str:
        return " ".join((
            self.tool, self.category, self.command, self.description,
            self.explanation, self.execution_context, self.caution or "",
        )).casefold()


@dataclass(frozen=True, slots=True)
class ExpandedReference:
    command: str
    missing: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.missing

    @property
    def guidance(self) -> str:
        if not self.missing:
            return "All required values are available."
        labels = {
            "name": "a selected target name",
            "identifier": "a selected application identifier",
            "pid": "a running target PID",
            "endpoint": "the configured Frida endpoint",
        }
        return "Required: " + ", ".join(labels.get(item, item) for item in self.missing) + "."


REFERENCE_COMMANDS = (
    ReferenceCommand(
        "Frida CLI", "Connection", "frida -H {endpoint} -n {identifier}",
        "Attach an interactive Frida REPL to a running application.",
        "Uses the same forwarded host endpoint as the live session launcher.",
        "Run in an external host terminal.", requires_target=True, requires_identifier=True,
    ),
    ReferenceCommand(
        "Frida CLI", "Connection", "frida -H {endpoint} -p {pid}",
        "Attach an interactive Frida REPL by PID.",
        "Useful when a process has no application identifier.",
        "Run in an external host terminal.", requires_target=True, requires_pid=True,
    ),
    ReferenceCommand(
        "Frida CLI", "Spawning", "frida -H {endpoint} -f {identifier}",
        "Spawn an application under Frida.",
        "Starts the selected package through frida-server.",
        "Run in an external host terminal.", changes_runtime=True,
        requires_target=True, requires_identifier=True,
        caution="Spawning changes application runtime state and may trigger startup behavior.",
    ),
    ReferenceCommand(
        "Frida CLI", "Tracing", "frida-trace -H {endpoint} -n {identifier} -i 'open*'",
        "Trace functions matching a pattern.",
        "The example traces functions whose names begin with open.",
        "Run in an external host terminal.", changes_runtime=True,
        requires_target=True, requires_identifier=True,
        caution="Tracing adds instrumentation hooks and can affect timing.",
    ),
    ReferenceCommand(
        "Frida CLI", "Discovery", "frida-ps -H {endpoint} -ai",
        "List installed and running applications.",
        "Shows application names, identifiers, and PIDs when running.",
        "Run in a host terminal; SUS Companion Target Refresh performs this for you.",
    ),
    ReferenceCommand(
        "Frida REPL", "Process", "Process.id",
        "Show the attached process ID.", "Reads Frida's current process metadata.",
        "Enter at the Frida REPL prompt.",
    ),
    ReferenceCommand(
        "Frida REPL", "Process", "Process.arch",
        "Show the process architecture.", "Common values include arm, arm64, ia32, and x64.",
        "Enter at the Frida REPL prompt.",
    ),
    ReferenceCommand(
        "Frida REPL", "Process", "Process.platform",
        "Show the current platform.", "Confirms the platform reported by the Frida runtime.",
        "Enter at the Frida REPL prompt.",
    ),
    ReferenceCommand(
        "Frida REPL", "Java", "Java.available",
        "Check whether the Java runtime is available.",
        "Run this before using Java-specific APIs.", "Enter at the Frida REPL prompt.",
    ),
    ReferenceCommand(
        "Frida REPL", "Java", "Java.androidVersion",
        "Show the Android version exposed by Frida's Java bridge.",
        "Only use this after Java.available returns true.", "Enter at the Frida REPL prompt.",
        caution="Java.androidVersion requires Java.available to be true.",
    ),
    ReferenceCommand(
        "Frida REPL", "Modules", "Process.enumerateModules()",
        "List modules loaded in the process.",
        "Returns module names, base addresses, sizes, and paths.", "Enter at the Frida REPL prompt.",
    ),
    ReferenceCommand(
        "Objection REPL", "Help", "help", "List available Objection commands.",
        "Use help followed by a command path for more detail.", "Enter at the Objection REPL prompt.",
    ),
    ReferenceCommand(
        "Objection REPL", "Environment", "env", "Show application environment information.",
        "Displays paths and runtime details for the attached application.",
        "Enter at the Objection REPL prompt.",
    ),
    ReferenceCommand(
        "Objection REPL", "Filesystem", "ls", "List the current application directory.",
        "Provides a read-only directory listing until a modifying filesystem command is used.",
        "Enter at the Objection REPL prompt.",
    ),
    ReferenceCommand(
        "Objection REPL", "Android", "android hooking list activities",
        "List Android activities.", "Inspects activities known to the attached application.",
        "Enter at the Objection REPL prompt.",
    ),
    ReferenceCommand(
        "Objection REPL", "Android", "android hooking list classes",
        "List loaded Java classes.", "May produce a large read-only class listing.",
        "Enter at the Objection REPL prompt.",
    ),
    ReferenceCommand(
        "Objection REPL", "Android", "android hooking watch class_method {identifier}.MainActivity.onCreate",
        "Watch calls to an Android method.", "Hooks the supplied method and reports invocations.",
        "Enter at the Objection REPL prompt.", changes_runtime=True,
        requires_target=True, requires_identifier=True,
        caution="Watching a method installs runtime hooks and may affect application timing.",
    ),
)


def reference_commands() -> tuple[ReferenceCommand, ...]:
    return REFERENCE_COMMANDS


def reference_categories(commands: Iterable[ReferenceCommand] = REFERENCE_COMMANDS) -> tuple[str, ...]:
    return tuple(sorted({command.category for command in commands}, key=str.casefold))


def filter_reference_commands(
    commands: Iterable[ReferenceCommand] = REFERENCE_COMMANDS,
    *, query: str = "", tool: str = "All", category: str = "All",
) -> tuple[ReferenceCommand, ...]:
    query_text = query.strip().casefold()
    tool_text = tool.strip().casefold()
    category_text = category.strip().casefold()
    return tuple(command for command in commands if (
        (tool_text == "all" or command.tool.casefold() == tool_text)
        and (category_text == "all" or command.category.casefold() == category_text)
        and (not query_text or query_text in command.search_text)
    ))


def expand_reference_command(
    command: ReferenceCommand,
    target: FridaTarget | None = None,
    endpoint: str = FridaSessionManager.ENDPOINT,
) -> ExpandedReference:
    values: Mapping[str, str | None] = {
        "name": target.name if target and target.name else None,
        "identifier": target.identifier if target and target.identifier else None,
        "pid": str(target.pid) if target and target.pid is not None else None,
        "endpoint": endpoint or None,
    }
    missing: list[str] = []
    expanded = command.command
    for placeholder, value in values.items():
        token = "{" + placeholder + "}"
        if token not in expanded:
            continue
        if value is None:
            missing.append(placeholder)
        else:
            expanded = expanded.replace(token, value)
    return ExpandedReference(expanded, tuple(missing))
