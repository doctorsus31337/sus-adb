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
    requires_fastboot_serial: bool = False
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
        "ANDROID PLATFORM TOOLS": (
            CommandSpec(
                "adb version", "Show the installed Android Debug Bridge version",
                "adb.version", "ADB", "Platform Tools",
                relationships=(_rel("adb.host-features"), _rel("fastboot.version")),
            ),
            CommandSpec(
                "adb host-features", "List features supported by the host ADB client",
                "adb.host-features", "ADB", "Platform Tools",
                relationships=(_rel("adb.features"), _rel("adb.version")),
            ),
            CommandSpec(
                "adb features", "List combined host and connected-device ADB features",
                "adb.features", "ADB", "Platform Tools",
                relationships=(_rel("adb.host-features"), _rel("adb.devices.long")),
            ),
            CommandSpec(
                "adb mdns services", "List locally advertised Wireless ADB services",
                "adb.mdns.services", "ADB", "Wireless Discovery",
                relationships=(_rel("adb.connect"), _rel("adb.disconnect.target")),
            ),
            CommandSpec(
                "adb connect <host>:<port>",
                "Connect ADB to an explicit host and numeric port",
                "adb.connect", "ADB", "Connection", impact="Local connection state",
                arguments=(
                    _arg("host>:<port", "Host or IP plus port 1–65535"),
                ),
                relationships=(
                    _rel("adb.disconnect.target"), _rel("adb.mdns.services"),
                ),
            ),
            CommandSpec(
                "adb disconnect", "Disconnect all host-managed TCP ADB transports",
                "adb.disconnect", "ADB", "Connection",
                impact="Local connection state",
                relationships=(_rel("adb.connect"), _rel("adb.devices.long")),
            ),
            CommandSpec(
                "adb disconnect <host>:<port>",
                "Disconnect one explicit host and numeric port",
                "adb.disconnect.target", "ADB", "Connection",
                impact="Local connection state",
                arguments=(
                    _arg("host>:<port", "Host or IP plus port 1–65535"),
                ),
                relationships=(_rel("adb.connect"), _rel("adb.mdns.services")),
            ),
            CommandSpec(
                "adb reconnect device", "Reconnect currently online ADB transports",
                "adb.reconnect.device", "ADB", "Connection",
                impact="Local connection state",
                relationships=(
                    _rel("adb.devices.long"), _rel("adb.reconnect.offline"),
                ),
            ),
            CommandSpec(
                "adb reconnect offline", "Reconnect only offline ADB transports",
                "adb.reconnect.offline", "ADB", "Connection",
                impact="Local connection state",
                relationships=(
                    _rel("adb.devices.long"), _rel("adb.reconnect.device"),
                ),
            ),
        ),
        "ADB SERVER & DISCOVERY": (
            CommandSpec(
                "adb devices", "List connected Android devices", "adb.devices",
                "ADB", "Discovery", aliases=("device list",),
                relationships=(
                    _rel("adb.devices.long"), _rel("adb.shell"),
                    _rel("adb.reboot.bootloader"), _rel("fastboot.devices"),
                ),
            ),
            CommandSpec(
                "adb devices -l", "List connected devices with transport details",
                "adb.devices.long", "ADB", "Discovery",
                aliases=("device details", "long device list"),
                relationships=(
                    _rel("adb.shell"), _rel("adb.get-state"), _rel("adb.reboot"),
                    _rel("adb.logcat.dump"), _rel("fastboot.devices"),
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
                requires_device=True,
                relationships=(_rel("adb.reboot"), _rel("fastboot.devices")),
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
        "FASTBOOT DISCOVERY": (
            CommandSpec(
                "fastboot --version", "Show the installed Fastboot version",
                "fastboot.version", "Fastboot", "Discovery",
                relationships=(_rel("fastboot.help"), _rel("fastboot.devices")),
            ),
            CommandSpec(
                "fastboot help", "Show Fastboot's local command help",
                "fastboot.help", "Fastboot", "Discovery",
                relationships=(_rel("fastboot.version"), _rel("fastboot.devices")),
            ),
            CommandSpec(
                "fastboot devices", "List devices visible to the Fastboot transport",
                "fastboot.devices", "Fastboot", "Discovery",
                relationships=(
                    _rel("fastboot.devices.long"),
                    _rel("fastboot.getvar.product"),
                    _rel("fastboot.getvar.current-slot"),
                ),
            ),
            CommandSpec(
                "fastboot devices -l",
                "List Fastboot devices with available transport details",
                "fastboot.devices.long", "Fastboot", "Discovery",
                relationships=(_rel("fastboot.devices"), _rel("adb.devices.long")),
            ),
        ),
        "FASTBOOT BOOTLOADER INFO": (
            CommandSpec(
                "fastboot -s <fastboot-serial> getvar <variable>",
                "Read one bounded bootloader variable from an explicit Fastboot serial",
                "fastboot.getvar", "Fastboot", "Bootloader Info",
                requires_fastboot_serial=True,
                arguments=(
                    _arg("fastboot-serial", "Explicit Fastboot transport serial"),
                    _arg("variable", "One bootloader metadata variable"),
                ),
                relationships=(_rel("fastboot.devices"), _rel("fastboot.getvar.all")),
            ),
            CommandSpec(
                "fastboot -s <fastboot-serial> getvar all",
                "Request all bootloader variables from an explicit Fastboot serial",
                "fastboot.getvar.all", "Fastboot", "Bootloader Info",
                classification="streaming-but-finite",
                requires_fastboot_serial=True,
                arguments=(
                    _arg("fastboot-serial", "Explicit Fastboot transport serial"),
                ),
                relationships=(_rel("fastboot.devices"), _rel("fastboot.getvar")),
            ),
            CommandSpec(
                "fastboot -s <fastboot-serial> getvar product",
                "Read the bootloader product identifier",
                "fastboot.getvar.product", "Fastboot", "Bootloader Info",
                requires_fastboot_serial=True, reference_only=True,
                arguments=(
                    _arg("fastboot-serial", "Explicit Fastboot transport serial"),
                ),
                relationships=(_rel("fastboot.getvar.current-slot"),),
            ),
            CommandSpec(
                "fastboot -s <fastboot-serial> getvar current-slot",
                "Read the current boot slot",
                "fastboot.getvar.current-slot", "Fastboot", "Bootloader Info",
                requires_fastboot_serial=True, reference_only=True,
                arguments=(
                    _arg("fastboot-serial", "Explicit Fastboot transport serial"),
                ),
                relationships=(_rel("fastboot.getvar.slot-count"),),
            ),
            CommandSpec(
                "fastboot -s <fastboot-serial> getvar slot-count",
                "Read the number of boot slots",
                "fastboot.getvar.slot-count", "Fastboot", "Bootloader Info",
                requires_fastboot_serial=True, reference_only=True,
                arguments=(
                    _arg("fastboot-serial", "Explicit Fastboot transport serial"),
                ),
                relationships=(_rel("fastboot.getvar.current-slot"),),
            ),
            *tuple(
                CommandSpec(
                    f"fastboot -s <fastboot-serial> getvar {variable}",
                    description,
                    f"fastboot.getvar.{variable}", "Fastboot", "Bootloader Info",
                    requires_fastboot_serial=True, reference_only=True,
                    arguments=(
                        _arg("fastboot-serial", "Explicit Fastboot transport serial"),
                    ),
                    relationships=(_rel("fastboot.devices"),),
                )
                for variable, description in (
                    ("serialno", "Read the bootloader-reported serial"),
                    ("secure", "Read the secure-bootloader state"),
                    ("unlocked", "Read the bootloader lock-state metadata"),
                    ("version-bootloader", "Read the bootloader version"),
                    ("version-baseband", "Read the baseband version"),
                    ("max-download-size", "Read the maximum download size"),
                )
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
                "objection -N -h 127.0.0.1 -P 27042 -n <target> start",
                "Attach Objection through an explicit forwarded network endpoint",
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
                    if spec.requires_fastboot_serial:
                        details.append(
                            "Context: Requires an operator-entered Fastboot serial; "
                            "the selected ADB serial is never reused"
                        )
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
