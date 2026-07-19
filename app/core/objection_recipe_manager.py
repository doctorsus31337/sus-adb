"""Local, confirmation-gated Objection startup recipe support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.command_result import CommandResult
from app.core.objection_manager import ObjectionManager


@dataclass(frozen=True, slots=True)
class ObjectionCapabilities:
    startup_script: bool = False
    startup_command: bool = False


@dataclass(frozen=True, slots=True)
class RecipeResult:
    ok: bool
    commands: tuple[str, ...] = ()
    launch_command: tuple[str, ...] = ()
    guidance: str | None = None
    error: str | None = None


class ObjectionRecipeManager:
    def __init__(self, objection: ObjectionManager, capability_provider):
        self.objection, self.capability_provider = objection, capability_provider

    @staticmethod
    def parse(text: str) -> tuple[str, ...]:
        return tuple(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(("#", ";")))

    def inspect_capabilities(self) -> ObjectionCapabilities:
        value = self.capability_provider()
        if isinstance(value, ObjectionCapabilities): return value
        text = str(getattr(value, "stdout", value)).casefold()
        return ObjectionCapabilities("--startup-script" in text, "--startup-command" in text)

    def prepare(self, target: str, transport: str, serial: str | None, recipe_path: str, text: str, *, confirmed: bool = False) -> RecipeResult:
        commands = self.parse(text)
        if not commands: return RecipeResult(False, error="The recipe contains no commands.")
        version = self.objection.version()
        if not version.ok: return RecipeResult(False, commands=commands, error=version.output)
        if not confirmed: return RecipeResult(False, commands=commands, error="Explicit launch confirmation is required.")
        capabilities = self.inspect_capabilities()
        base = self.objection.build_attach_command(target, transport, serial)
        if capabilities.startup_script:
            return RecipeResult(True, commands, (*base[:-1], "--startup-script", recipe_path, base[-1]))
        if capabilities.startup_command and len(commands) == 1:
            return RecipeResult(True, commands, (*base[:-1], "--startup-command", commands[0], base[-1]))
        return RecipeResult(False, commands=commands, guidance="This Objection version cannot launch the complete recipe automatically. Copy the displayed commands into the REPL in order.", error="Supported startup options are unavailable.")

    def launch(self, prepared: RecipeResult) -> CommandResult:
        if not prepared.ok or not prepared.launch_command:
            return CommandResult.from_command(prepared.launch_command, -1, error=prepared.error or prepared.guidance or "Recipe is not launchable.")
        return self.objection.launch_external_session(prepared.launch_command)
