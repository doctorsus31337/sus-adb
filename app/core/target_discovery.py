"""Structured Frida application and process discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections.abc import Iterable

from app.core.command_result import CommandResult
from app.core.frida_manager import FridaManager
from app.core.frida_target import FridaTarget, TargetType


@dataclass(frozen=True, slots=True)
class TargetDiscoveryResult:
    serial: str | None
    targets: tuple[FridaTarget, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    command_results: tuple[CommandResult, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.errors


class TargetDiscovery:
    _SEPARATOR = re.compile(r"^[\s-]+$")
    _IDENTIFIER = re.compile(r"^[^\s.]+(?:\.[^\s.]+)+$")

    def __init__(self, frida: FridaManager):
        self.frida = frida

    def discover_applications(self, serial: str | None) -> TargetDiscoveryResult:
        return self._discover(serial, TargetType.APPLICATION)

    def discover_processes(self, serial: str | None) -> TargetDiscoveryResult:
        return self._discover(serial, TargetType.PROCESS)

    def discover_combined(self, serial: str | None) -> TargetDiscoveryResult:
        if not serial:
            return TargetDiscoveryResult(None, errors=("No device is selected.",))
        applications = self.discover_applications(serial)
        processes = self.discover_processes(serial)
        combined = list(applications.targets)
        application_pids = {target.pid for target in combined if target.pid is not None}
        for target in processes.targets:
            if target.pid is not None and target.pid in application_pids:
                continue
            combined.append(target)
        return TargetDiscoveryResult(
            serial,
            self._deduplicate_and_sort(combined),
            applications.errors + processes.errors,
            applications.command_results + processes.command_results,
        )

    def _discover(self, serial: str | None, target_type: TargetType) -> TargetDiscoveryResult:
        if not serial:
            return TargetDiscoveryResult(None, errors=("No device is selected.",))
        try:
            result = (
                self.frida.list_applications(serial)
                if target_type is TargetType.APPLICATION
                else self.frida.list_processes(serial)
            )
        except Exception as exc:
            return TargetDiscoveryResult(serial, errors=(str(exc),))
        if not result.ok:
            return TargetDiscoveryResult(
                serial, errors=(result.output or "Frida target discovery failed.",),
                command_results=(result,),
            )
        targets = self.parse_output(result.stdout, target_type)
        return TargetDiscoveryResult(serial, targets, command_results=(result,))

    @classmethod
    def parse_applications(cls, output: str) -> tuple[FridaTarget, ...]:
        return cls.parse_output(output, TargetType.APPLICATION)

    @classmethod
    def parse_processes(cls, output: str) -> tuple[FridaTarget, ...]:
        return cls.parse_output(output, TargetType.PROCESS)

    @classmethod
    def parse_output(cls, output: str, target_type: TargetType) -> tuple[FridaTarget, ...]:
        targets: list[FridaTarget] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line or cls._is_heading(line):
                continue
            target = cls._parse_application(line) if target_type is TargetType.APPLICATION else cls._parse_process(line)
            if target is not None:
                targets.append(target)
        return cls._deduplicate_and_sort(targets)

    @classmethod
    def _parse_application(cls, line: str) -> FridaTarget | None:
        parts = line.split()
        if not parts:
            return None
        pid: int | None = None
        if parts[0].isdigit():
            pid = int(parts.pop(0))
        elif parts[0] == "-":
            parts.pop(0)
        if not parts:
            return None
        identifier = parts[-1] if cls._IDENTIFIER.match(parts[-1]) else None
        if identifier:
            parts.pop()
        name = " ".join(parts).strip()
        if not identifier:
            return None
        return FridaTarget(name, identifier, pid, TargetType.APPLICATION, pid is not None)

    @staticmethod
    def _parse_process(line: str) -> FridaTarget | None:
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].strip():
            return None
        pid = int(parts[0])
        return FridaTarget(parts[1].strip(), None, pid, TargetType.PROCESS, True)

    @classmethod
    def _is_heading(cls, line: str) -> bool:
        lowered = line.casefold()
        return bool(cls._SEPARATOR.match(line)) or (
            "pid" in lowered and "name" in lowered
        ) or lowered.startswith("failed to enumerate")

    @staticmethod
    def _deduplicate_and_sort(targets: Iterable[FridaTarget]) -> tuple[FridaTarget, ...]:
        unique: dict[tuple, FridaTarget] = {}
        for target in targets:
            if target.target_type is TargetType.APPLICATION:
                key = (target.target_type, target.identifier or target.name)
            else:
                key = (target.target_type, target.pid if target.pid is not None else target.name)
            existing = unique.get(key)
            if existing is None or (target.running and not existing.running):
                unique[key] = target
        return tuple(sorted(
            unique.values(),
            key=lambda target: (
                0 if target.target_type is TargetType.APPLICATION else 1,
                (target.name or target.identifier or "").casefold(),
                target.identifier or "",
                target.pid if target.pid is not None else -1,
            ),
        ))


def filter_targets(
    targets: Iterable[FridaTarget], query: str = "", target_type: str = "all"
) -> tuple[FridaTarget, ...]:
    normalized_query = query.strip().casefold()
    normalized_type = target_type.strip().casefold()
    filtered = []
    for target in targets:
        if normalized_type in {"application", "applications"} and target.target_type is not TargetType.APPLICATION:
            continue
        if normalized_type in {"process", "processes"} and target.target_type is not TargetType.PROCESS:
            continue
        haystack = " ".join((target.name, target.identifier or "", str(target.pid or ""))).casefold()
        if normalized_query and normalized_query not in haystack:
            continue
        filtered.append(target)
    return tuple(filtered)
