"""GUI-neutral, non-executing contextual command completion."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from app.core.command_registry import CommandRegistry, CommandSpec


class CompletionMode(str, Enum):
    HIDDEN = "hidden"
    PREFIX = "prefix"
    CONTEXT = "context"
    RELATED = "related"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class CommandCompletionContext:
    selected_serial: str = ""
    selected_device_state: str = ""
    selected_target: str = ""
    platform: str = os.name
    tool_availability: tuple[tuple[str, bool | None], ...] = ()
    cwd: str = ""

    @property
    def tools(self) -> Mapping[str, bool | None]:
        return dict(self.tool_availability)


@dataclass(frozen=True, slots=True)
class PartialCommand:
    text: str
    cursor: int
    tokens: tuple[str, ...]
    replacement_start: int
    replacement_end: int
    unfinished_quote: str = ""


@dataclass(frozen=True, slots=True)
class CommandSuggestion:
    command_id: str
    command_text: str
    display_syntax: str
    description: str
    family: str
    category: str
    aliases: tuple[str, ...]
    classification: str
    impact: str
    opens_session: bool
    requires_device: bool
    requires_fastboot_serial: bool
    uses_target: bool
    placeholders: tuple[str, ...]
    related_command_ids: tuple[str, ...]
    replacement_span: tuple[int, int]
    reason: str
    rank: tuple[object, ...]
    cursor_offset: int

    @property
    def related(self) -> bool:
        return self.reason == "Related command"

    def apply(self, source: str) -> tuple[str, int]:
        start, end = self.replacement_span
        value = source[:start] + self.command_text + source[end:]
        return value, start + self.cursor_offset


@dataclass(frozen=True, slots=True)
class CommandSuggestionResult:
    suggestions: tuple[CommandSuggestion, ...] = ()
    total_count: int = 0
    mode: CompletionMode = CompletionMode.HIDDEN
    heading: str = ""
    context_note: str = ""
    common_prefix: str = ""


def parse_partial_command(text: object, cursor: int | None = None) -> PartialCommand:
    """Tokenize incomplete text without evaluating or expanding it."""
    source = str(text or "")
    position = len(source) if cursor is None else min(max(0, int(cursor)), len(source))
    prefix = source[:position]
    tokens: list[str] = []
    token: list[str] = []
    quote = ""
    escaped = False
    for character in prefix:
        if escaped:
            token.append(character)
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif quote:
            if character == quote:
                quote = ""
            else:
                token.append(character)
        elif character in {"'", '"'}:
            quote = character
        elif character.isspace():
            if token:
                tokens.append("".join(token))
                token.clear()
        else:
            token.append(character)
    if escaped:
        token.append("\\")
    if token or quote:
        tokens.append("".join(token))
    start = next((index for index, value in enumerate(prefix) if not value.isspace()), position)
    return PartialCommand(source, position, tuple(tokens), start, position, quote)


def _template_tokens(value: str) -> tuple[str, ...]:
    return tuple(value.split())


def _is_placeholder(value: str) -> bool:
    return len(value) > 2 and value.startswith("<") and value.endswith(">")


def _quote(value: str, platform: str) -> str:
    if platform.casefold() in {"nt", "windows", "win32"}:
        return subprocess.list2cmdline((value,))
    return shlex.quote(value)


def _materialize(
    spec: CommandSpec,
    context: CommandCompletionContext,
    supplied_tokens: tuple[str, ...] = (),
) -> tuple[str, tuple[str, ...], int]:
    output: list[str] = []
    unresolved: list[str] = []
    cursor_offset = -1
    arguments = {argument.name: argument for argument in spec.arguments}
    for index, token in enumerate(_template_tokens(spec.command)):
        if not _is_placeholder(token):
            output.append(token)
            continue
        name = token[1:-1]
        argument = arguments.get(name)
        value = ""
        if index < len(supplied_tokens) and supplied_tokens[index]:
            value = supplied_tokens[index]
        elif argument and argument.context_key == "selected_target":
            value = context.selected_target
        elif argument and argument.context_key == "selected_serial":
            value = context.selected_serial
        if value:
            output.append(_quote(value, context.platform))
        else:
            unresolved.append(name)
            if cursor_offset < 0:
                cursor_offset = len(" ".join(output)) + (1 if output else 0)
            break
    command = " ".join(output)
    if unresolved and command:
        command += " "
    if cursor_offset < 0:
        cursor_offset = len(command)
    return command, tuple(unresolved), cursor_offset


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _match_stage(spec: CommandSpec, query: str, query_tokens: tuple[str, ...]) -> tuple[int, int] | None:
    syntax = _normalized(spec.command)
    syntax_tokens = _template_tokens(syntax)
    if not query:
        return None
    if query_tokens:
        prior = query_tokens[:-1]
        current = query_tokens[-1].casefold()
        if (
            len(query_tokens) <= len(syntax_tokens)
            and all(
                _is_placeholder(right)
                or left.casefold() == right.casefold()
                for left, right in zip(prior, syntax_tokens)
            )
            and (
                _is_placeholder(syntax_tokens[len(query_tokens) - 1])
                or syntax_tokens[len(query_tokens) - 1].casefold().startswith(current)
            )
        ):
            expected = syntax_tokens[len(query_tokens) - 1]
            return (
                0,
                0 if _is_placeholder(expected) else len(expected) - len(current),
            )
    if syntax.startswith(query):
        return 1, len(syntax) - len(query)
    if query.endswith(" ") and syntax.startswith(query.rstrip()):
        return 2, len(syntax) - len(query)
    for index, alias in enumerate(spec.aliases):
        normalized_alias = _normalized(alias)
        if normalized_alias == query or normalized_alias.startswith(query):
            return 5, index
    return None


class CommandCompletionService:
    """Deterministic registry projection; never performs I/O or execution."""

    def __init__(
        self,
        registry=CommandRegistry,
        *,
        visible_limit: int = 10,
        specs: Iterable[CommandSpec] | None = None,
    ):
        self.registry = registry
        self.visible_limit = min(12, max(1, int(visible_limit)))
        self._specs = tuple(specs if specs is not None else registry.specs())
        self._by_id = {spec.command_id: spec for spec in self._specs}

    def suggest(
        self,
        text: object,
        context: CommandCompletionContext | None = None,
        *,
        cursor: int | None = None,
        manual: bool = False,
    ) -> CommandSuggestionResult:
        snapshot = context or CommandCompletionContext()
        parsed = parse_partial_command(text, cursor)
        query = _normalized(parsed.text[parsed.replacement_start:parsed.cursor])
        if not query and not manual:
            return CommandSuggestionResult()

        exact = next(
            (
                spec for spec in self._specs
                if not spec.arguments and _normalized(spec.command) == query
            ),
            None,
        )
        if (
            exact
            and exact.relationships
            and exact.command_id != "adb.reconnect"
        ):
            related = tuple(
                self._suggestion(
                    self._by_id[relationship.command_id], snapshot, parsed,
                    (4, order), "Related command",
                )
                for order, relationship in enumerate(exact.relationships)
                if relationship.command_id in self._by_id
            )
            return CommandSuggestionResult(
                related[: self.visible_limit], len(related), CompletionMode.RELATED,
                f"Related {exact.family} commands", self._context_note(snapshot),
                self._common_prefix(related),
            )

        matches: list[CommandSuggestion] = []
        query_tokens = tuple(query.split())
        for order, spec in enumerate(self._specs):
            stage = _match_stage(spec, query, query_tokens)
            if stage is None and manual and not query:
                stage = (6, order)
            if stage is None:
                continue
            reason = {
                0: "Current token prefix",
                1: "Full command prefix",
                2: "Next token completion",
                5: "Alias/search term match",
                6: "Manual command list",
            }[stage[0]]
            matches.append(
                self._suggestion(spec, snapshot, parsed, (*stage, order), reason)
            )

        contextual = self._selected_serial_suggestion(query, snapshot, parsed)
        if contextual is not None:
            matches.append(contextual)
        unique = []
        seen_commands = set()
        for item in sorted(matches, key=lambda value: value.rank):
            if item.command_text in seen_commands:
                continue
            seen_commands.add(item.command_text)
            unique.append(item)
        ordered = tuple(unique)
        mode = CompletionMode.MANUAL if manual and not query else CompletionMode.PREFIX
        return CommandSuggestionResult(
            ordered[: self.visible_limit], len(ordered), mode,
            "Command suggestions", self._context_note(snapshot),
            self._common_prefix(ordered),
        )

    def _suggestion(self, spec, context, parsed, rank, reason):
        command, unresolved, cursor_offset = _materialize(
            spec, context, parsed.tokens
        )
        if spec.uses_target and context.selected_target and not unresolved:
            rank = (3, *rank)
            reason = "Current selected target"
        tool = _template_tokens(spec.command)[0]
        availability = context.tools.get(tool)
        description = spec.description
        if availability is False:
            description += " · Tool unavailable"
        elif spec.opens_session:
            description += " · Opens in Sessions Center"
        elif spec.requires_device and not context.selected_serial:
            description += " · No device selected"
        return CommandSuggestion(
            spec.command_id, command, spec.command, description, spec.family,
            spec.category, spec.aliases, spec.classification, spec.impact,
            spec.opens_session, spec.requires_device,
            spec.requires_fastboot_serial, spec.uses_target,
            unresolved, tuple(item.command_id for item in spec.relationships),
            (parsed.replacement_start, parsed.replacement_end), reason,
            tuple(rank) + (spec.command.casefold(), spec.command_id),
            cursor_offset,
        )

    def _selected_serial_suggestion(self, query, context, parsed):
        if not context.selected_serial or not (
            query == "adb -s" or query.startswith("adb -s ")
        ):
            return None
        command = f"adb -s {_quote(context.selected_serial, context.platform)} "
        return CommandSuggestion(
            "context.selected-device", command, command.rstrip(),
            "Insert the current selected device serial", "ADB", "Context",
            (), "one-shot", "Read-only", False, True, False, False, (),
            (), (parsed.replacement_start, parsed.replacement_end),
            "Current selected device", (3, 0, command.casefold()),
            len(command),
        )

    @staticmethod
    def _context_note(context):
        if context.selected_serial:
            state = f" · {context.selected_device_state}" if context.selected_device_state else ""
            return f"Selected device: {context.selected_serial}{state}"
        return "No device selected"

    @staticmethod
    def _common_prefix(suggestions):
        values = tuple(item.command_text for item in suggestions)
        if not values:
            return ""
        prefix = os.path.commonprefix(values)
        if not prefix:
            return ""
        if len(prefix) < min(len(value) for value in values):
            boundary = max(prefix.rfind(" "), prefix.rfind("-") + 1)
            if boundary > 0 and not all(value.startswith(prefix) for value in values):
                prefix = prefix[:boundary]
        return prefix
