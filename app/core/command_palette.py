"""GUI-neutral command model and deterministic palette search."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass(frozen=True, slots=True)
class PaletteCommand:
    """One immutable, stable navigation destination."""

    command_id: str
    title: str
    description: str
    category: str
    aliases: tuple[str, ...] = ()
    keyboard_hint: str = ""
    available: bool = True
    unavailable_reason: str = ""
    destination: str = ""
    result_type: str = "navigation"
    technical_context: str = ""
    default_rank: int = 100
    invoke: Callable[[str], object] = field(
        default=lambda _query: None, compare=False, repr=False
    )


@dataclass(frozen=True, slots=True)
class PaletteMatch:
    command: PaletteCommand
    rank: tuple[object, ...]


def _ordered_fuzzy(needle: str, haystack: str) -> tuple[int, int] | None:
    position = -1
    first = -1
    gaps = 0
    for character in needle:
        found = haystack.find(character, position + 1)
        if found < 0:
            return None
        if first < 0:
            first = found
        elif found > position + 1:
            gaps += found - position - 1
        position = found
    return gaps, first


def _match_rank(command: PaletteCommand, query: str) -> tuple[int, int] | None:
    title = command.title.casefold()
    aliases = tuple(alias.casefold() for alias in command.aliases)
    primary = (title, *aliases)
    if query in primary:
        return 0, primary.index(query)
    if title.startswith(query):
        return 1, 0
    alias_prefix = next(
        (index for index, alias in enumerate(aliases) if alias.startswith(query)),
        None,
    )
    if alias_prefix is not None:
        return 1, alias_prefix + 1
    words = tuple(
        word
        for value in (
            title,
            *aliases,
            command.description.casefold(),
            command.category.casefold(),
        )
        for word in value.replace("—", " ").replace("/", " ").split()
    )
    word_prefix = next(
        (index for index, word in enumerate(words) if word.startswith(query)),
        None,
    )
    if word_prefix is not None:
        return 2, word_prefix
    searchable = " ".join(
        (
            title,
            *aliases,
            command.description.casefold(),
            command.category.casefold(),
            command.technical_context.casefold(),
        )
    )
    substring = searchable.find(query)
    if substring >= 0:
        return 3, substring
    fuzzy = _ordered_fuzzy(query, searchable)
    if fuzzy is not None:
        return 4, fuzzy[0] * 1000 + fuzzy[1]
    return None


class CommandPaletteRegistry:
    """Runtime registry with bounded recents and stable ranking."""

    def __init__(self, commands: Iterable[PaletteCommand] = (), recent_limit=8):
        self._commands: tuple[PaletteCommand, ...] = ()
        self._by_id: dict[str, PaletteCommand] = {}
        self._recent: list[str] = []
        self.recent_limit = max(1, int(recent_limit))
        self.replace(commands)

    @property
    def commands(self) -> tuple[PaletteCommand, ...]:
        return self._commands

    @property
    def recent_ids(self) -> tuple[str, ...]:
        return tuple(self._recent)

    def replace(self, commands: Iterable[PaletteCommand]) -> None:
        values = tuple(commands)
        identifiers = tuple(command.command_id for command in values)
        if any(not identifier for identifier in identifiers):
            raise ValueError("Palette command IDs must be non-empty.")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Palette command IDs must be unique.")
        self._commands = values
        self._by_id = dict(zip(identifiers, values))
        self._recent[:] = [
            command_id for command_id in self._recent if command_id in self._by_id
        ]

    def search(self, query: object = "", limit=16) -> tuple[PaletteMatch, ...]:
        bounded = max(1, int(limit))
        normalized = " ".join(str(query or "").casefold().split())
        recent_order = {
            command_id: index for index, command_id in enumerate(self._recent)
        }
        matches = []
        for order, command in enumerate(self._commands):
            if normalized:
                match = _match_rank(command, normalized)
                if match is None:
                    continue
                stage, quality = match
            else:
                if (
                    command.command_id not in recent_order
                    and command.category not in {"Workspaces", "Tools"}
                ):
                    continue
                stage = 0 if command.command_id in recent_order else 1
                quality = (
                    recent_order.get(command.command_id, command.default_rank)
                )
            recent_tie = recent_order.get(command.command_id, self.recent_limit + 1)
            rank = (
                stage,
                quality,
                recent_tie,
                command.default_rank,
                command.category.casefold(),
                command.title.casefold(),
                command.command_id,
                order,
            )
            matches.append(PaletteMatch(command, rank))
        return tuple(sorted(matches, key=lambda item: item.rank)[:bounded])

    def invoke(self, command_id: str, query: str = "") -> object:
        command = self._by_id.get(command_id)
        if command is None or not command.available:
            return None
        if command_id in self._recent:
            self._recent.remove(command_id)
        self._recent.insert(0, command_id)
        del self._recent[self.recent_limit :]
        return command.invoke(query)
