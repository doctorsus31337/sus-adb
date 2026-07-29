"""Canonical command metadata shared by execution guidance and completion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandArgumentSpec:
    """One unresolved value in a command template."""

    name: str
    description: str
    context_key: str = ""
    required: bool = True


@dataclass(frozen=True, slots=True)
class CommandRelationship:
    """An explicit, deterministic relationship to another registry command."""

    command_id: str
    reason: str = "Related command"


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Immutable metadata for one command understood by the host architecture."""

    command: str
    description: str
    command_id: str = ""
    family: str = ""
    category: str = ""
    aliases: tuple[str, ...] = ()
    classification: str = "one-shot"
    impact: str = "Read-only"
    opens_session: bool = False
    requires_device: bool = False
    uses_target: bool = False
    arguments: tuple[CommandArgumentSpec, ...] = ()
    relationships: tuple[CommandRelationship, ...] = ()
    reference_only: bool = False

    @property
    def syntax(self) -> str:
        return self.command

    @property
    def placeholders(self) -> tuple[str, ...]:
        return tuple(argument.name for argument in self.arguments)

    @property
    def search_terms(self) -> tuple[str, ...]:
        return (self.command, self.description, self.family, self.category, *self.aliases)


def _arg(name: str, description: str, context_key: str = "") -> CommandArgumentSpec:
    return CommandArgumentSpec(name, description, context_key)


def _rel(command_id: str) -> CommandRelationship:
    return CommandRelationship(command_id)


class CommandRegistry:
    """Single source of truth for supported commands and reference guidance."""

    COMMANDS: dict[str, tuple[CommandSpec, ...]] = {
        "SUS COMPANION": (
            CommandSpec(
                "help", "Show the canonical command reference", "sus.help",
                "SUS Companion", "Console", aliases=("commands", "reference"),
            ),
            CommandSpec(
                "clear", "Clear the integrated console", "sus.clear",
                "SUS Companion", "Console", aliases=("cls",), impact="Local state",
            ),
            CommandSpec(
                "stop", "Show the current terminal cancellation status", "sus.stop",
                "SUS Companion", "Console", impact="Local state",
            ),
            CommandSpec(
                "cd <directory>", "Change the integrated command working directory",
                "sus.cd", "SUS Companion", "Console", aliases=("change directory",),
                impact="Local state", arguments=(_arg("directory", "Working directory"),),
            ),
        ),
        "ADB SERVER & DISCOVERY": (
            CommandSpec(
                "adb devices", "List connected Android devices", "adb.devices",
                "ADB", "Discovery", aliases=("device list",),
                relationships=(_rel("adb.devices.long"), _rel("adb.shell")),
            ),
            CommandSpec(
                "adb devices -l", "List connected devices with transport details",
                "adb.devices.long", "ADB", "Discovery",
                aliases=("device details", "long device list"),
                relationships=(
                    _rel("adb.shell"), _rel("adb.get-state"), _rel("adb.reboot"),
                    _rel("adb.logcat.dump"),
                ),
            ),
            CommandSpec(
                "adb start-server", "Start the local ADB server", "adb.start-server",
                "ADB", "Server", impact="State-changing",
                relationships=(
                    _rel("adb.devices.long"), _rel("adb.reconnect"),
                    _rel("adb.kill-server"),
                ),
            ),
            CommandSpec(
                "adb kill-server", "Stop the local ADB server", "adb.kill-server",
                "ADB", "Server", impact="State-changing",
                relationships=(_rel("adb.start-server"), _rel("adb.reconnect")),
            ),
            CommandSpec(
                "adb reconnect", "Reconnect ADB transports", "adb.reconnect",
                "ADB", "Server", impact="State-changing",
                relationships=(_rel("adb.devices.long"), _rel("adb.start-server")),
            ),
            CommandSpec(
                "adb get-state", "Print the selected/default device state",
                "adb.get-state", "ADB", "Device", requires_device=True,
                relationships=(_rel("adb.devices.long"), _rel("adb.get-serialno")),
            ),
            CommandSpec(
                "adb get-serialno", "Print the selected/default device serial",
                "adb.get-serialno", "ADB", "Device", requires_device=True,
                relationships=(_rel("adb.get-state"), _rel("adb.devices.long")),
            ),
        ),
        "ADB DEVICE & SESSION": (
            CommandSpec(
                "adb shell", "Open an interactive Android shell in a dedicated session",
                "adb.shell", "ADB", "Sessions", classification="interactive",
                opens_session=True, requires_device=True,
                relationships=(_rel("adb.devices.long"), _rel("adb.logcat")),
            ),
            CommandSpec(
                "adb reboot", "Reboot the selected/default device", "adb.reboot",
                "ADB", "Device", impact="State-changing", requires_device=True,
                relationships=(_rel("adb.reboot.recovery"), _rel("adb.reboot.bootloader")),
            ),
            CommandSpec(
                "adb reboot recovery", "Reboot the device into recovery",
                "adb.reboot.recovery", "ADB", "Device", impact="State-changing",
                requires_device=True, relationships=(_rel("adb.reboot"),),
            ),
            CommandSpec(
                "adb reboot bootloader", "Reboot the device into the bootloader",
                "adb.reboot.bootloader", "ADB", "Device", impact="State-changing",
                requires_device=True, relationships=(_rel("adb.reboot"),),
            ),
            CommandSpec(
                "adb logcat", "Open live Logcat in a dedicated session", "adb.logcat",
                "ADB", "Logs", classification="interactive", opens_session=True,
                requires_device=True,
                relationships=(_rel("adb.logcat.dump"), _rel("adb.logcat.clear")),
            ),
            CommandSpec(
                "adb logcat -d", "Dump the current Logcat buffer", "adb.logcat.dump",
                "ADB", "Logs", classification="streaming-but-finite",
                requires_device=True,
                relationships=(_rel("adb.logcat"), _rel("adb.logcat.clear")),
            ),
            CommandSpec(
                "adb logcat -c", "Clear the current Logcat buffer", "adb.logcat.clear",
                "ADB", "Logs", classification="interactive",
                impact="State-changing", opens_session=True, requires_device=True,
                relationships=(_rel("adb.logcat"), _rel("adb.logcat.dump")),
            ),
        ),
        "ADB TRANSFER & PACKAGES": (
            CommandSpec(
                "adb pull <remote> <local>", "Pull a device file to a chosen local path",
                "adb.pull", "ADB", "Transfer", classification="streaming-but-finite",
                requires_device=True,
                arguments=(
                    _arg("remote", "Remote device path"),
                    _arg("local", "Local destination path"),
                ),
            ),
            CommandSpec(
                "adb push <local> <remote>", "Push a chosen local file to the device",
                "adb.push", "ADB", "Transfer", classification="streaming-but-finite",
                impact="State-changing", requires_device=True,
                arguments=(
                    _arg("local", "Local source path"),
                    _arg("remote", "Remote device path"),
                ),
            ),
            CommandSpec(
                "adb install <apk>", "Install a chosen APK on the device", "adb.install",
                "ADB", "Packages", classification="streaming-but-finite",
                impact="State-changing", requires_device=True,
                arguments=(_arg("apk", "Local APK path"),),
            ),
            CommandSpec(
                "adb uninstall <package>", "Uninstall an explicit package identifier",
                "adb.uninstall", "ADB", "Packages", impact="State-changing",
                requires_device=True,
                arguments=(_arg("package", "Package identifier", "selected_target"),),
            ),
            CommandSpec(
                "adb bugreport <destination>", "Write an ADB bugreport to a chosen destination",
                "adb.bugreport", "ADB", "Diagnostics",
                classification="streaming-but-finite", requires_device=True,
                arguments=(_arg("destination", "Local destination path"),),
            ),
        ),
        "FRIDA": (
            CommandSpec(
                "frida-ps -H 127.0.0.1:27042", "List processes through forwarded Frida ports",
                "frida.processes", "Frida", "Discovery",
                aliases=("frida process discovery", "process list"),
                relationships=(
                    _rel("frida.attach"), _rel("frida.trace"), _rel("objection.attach"),
                ),
            ),
            CommandSpec(
                "frida-ps -H 127.0.0.1:27042 -ai",
                "List applications and identifiers through forwarded Frida ports",
                "frida.applications", "Frida", "Discovery",
                aliases=("frida apps", "application discovery"),
                relationships=(_rel("frida.attach"), _rel("objection.attach")),
            ),
            CommandSpec(
                "frida -H 127.0.0.1:27042 -n <target>",
                "Attach Frida to the selected or explicit process target",
                "frida.attach", "Frida", "Sessions", aliases=("frida attach",),
                classification="interactive", opens_session=True, requires_device=True,
                uses_target=True,
                arguments=(_arg("target", "Process or application target", "selected_target"),),
                relationships=(_rel("frida.processes"), _rel("frida.trace"), _rel("objection.attach")),
            ),
            CommandSpec(
                "frida-trace -H 127.0.0.1:27042 -n <target>",
                "Trace functions on the selected or explicit target",
                "frida.trace", "Frida", "Sessions", aliases=("frida trace",),
                classification="interactive", opens_session=True, requires_device=True,
                uses_target=True,
                arguments=(_arg("target", "Process or application target", "selected_target"),),
                relationships=(_rel("frida.processes"), _rel("frida.attach")),
            ),
        ),
        "OBJECTION": (
            CommandSpec(
                "objection version", "Show the installed Objection version",
                "objection.version", "Objection", "Discovery",
            ),
            CommandSpec(
                "objection -S socket -n <target> start",
                "Attach Objection through the forwarded Frida socket",
                "objection.attach", "Objection", "Sessions",
                aliases=("objection start", "objection attach"),
                classification="interactive", opens_session=True, requires_device=True,
                uses_target=True,
                arguments=(_arg("target", "Application or process target", "selected_target"),),
                relationships=(_rel("frida.processes"), _rel("frida.attach")),
            ),
        ),
    }

    @classmethod
    def grouped(cls) -> dict[str, tuple[CommandSpec, ...]]:
        return cls.COMMANDS

    @classmethod
    def specs(cls) -> tuple[CommandSpec, ...]:
        return tuple(spec for group in cls.COMMANDS.values() for spec in group)

    @classmethod
    def by_id(cls) -> dict[str, CommandSpec]:
        return {spec.command_id: spec for spec in cls.specs()}

    @classmethod
    def all_commands(cls) -> list[str]:
        return [spec.command for spec in cls.specs()]

    @classmethod
    def render_text(cls, *, advanced: bool = False) -> str:
        lines = ["SUS COMPANION COMMAND REFERENCE", ""]
        for group_name, commands in cls.COMMANDS.items():
            lines.append(f"=== {group_name} ===")
            for spec in commands:
                lines.append(spec.command)
                lines.append(f"  {spec.description}")
                if advanced:
                    details = [
                        f"Category: {spec.category}",
                        f"Classification: {spec.classification}",
                        f"Impact: {spec.impact}",
                    ]
                    if spec.arguments:
                        details.append(
                            "Values: " + ", ".join(
                                f"<{argument.name}> — {argument.description}"
                                for argument in spec.arguments
                            )
                        )
                    if spec.requires_device:
                        details.append("Context: Uses the explicit selected device")
                    if spec.uses_target:
                        details.append("Context: Can use the explicit selected target")
                    if spec.opens_session:
                        details.append("Routing: Opens in Sessions Center")
                    if spec.relationships:
                        related = cls.by_id()
                        details.append(
                            "Related: " + ", ".join(
                                related[item.command_id].command
                                for item in spec.relationships
                                if item.command_id in related
                            )
                        )
                    lines.extend(f"  {detail}" for detail in details)
            lines.append("")
        lines.extend((
            "Suggestions insert text only. Run or Enter is always required.",
            "Dynamic device and target values come only from current in-memory selection.",
            "Filesystem completion is not supported.",
            "",
            "Prompt: sus-companion >",
            "Legacy CLI: sus-adb",
            "",
            "⚔ Hack the Castle ⚔",
        ))
        return "\n".join(lines)
