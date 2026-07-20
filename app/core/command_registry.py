"""Single source of truth for commands shown by SUS-ADB."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandSpec:
    command: str
    description: str


class CommandRegistry:
    COMMANDS: dict[str, tuple[CommandSpec, ...]] = {
        "SUS-ADB": (
            CommandSpec("help", "Show this command reference"),
            CommandSpec("clear", "Clear the integrated console"),
            CommandSpec("stop", "Stop the currently running terminal command"),
        ),
        "ADB": (
            CommandSpec("adb devices -l", "List connected Android devices"),
            CommandSpec("adb shell", "Open an interactive Android shell externally"),
            CommandSpec("adb reboot", "Reboot the selected/default device"),
            CommandSpec("adb reboot recovery", "Reboot into recovery"),
            CommandSpec("adb reboot bootloader", "Reboot into bootloader"),
            CommandSpec("adb logcat -d", "Dump the current Logcat buffer"),
            CommandSpec("adb logcat -c", "Clear the Logcat buffer"),
        ),
        "FRIDA": (
            CommandSpec("frida-ps -H 127.0.0.1:27042", "List processes through forwarded Frida ports"),
            CommandSpec("frida-ps -H 127.0.0.1:27042 -ai", "List installed applications and identifiers through forwarded Frida ports"),
            CommandSpec('frida -H 127.0.0.1:27042 -n "AppName"', "Attach Frida by process name"),
        ),
        "OBJECTION": (
            CommandSpec("objection version", "Show the installed Objection version"),
            CommandSpec("objection -S socket -n AppName start", "Attach using the forwarded Frida socket"),
        ),
    }

    @classmethod
    def grouped(cls) -> dict[str, tuple[CommandSpec, ...]]:
        return cls.COMMANDS

    @classmethod
    def all_commands(cls) -> list[str]:
        return [spec.command for group in cls.COMMANDS.values() for spec in group]

    @classmethod
    def render_text(cls) -> str:
        lines = ["SUS-ADB QUICK COMMANDS", ""]
        for group_name, commands in cls.COMMANDS.items():
            lines.append(f"=== {group_name} ===")
            for spec in commands:
                lines.append(spec.command)
                lines.append(f"  {spec.description}")
            lines.append("")
        lines.extend(("Prompt: sus-adb >", "", "⚔ Hack the Castle ⚔"))
        return "\n".join(lines)
