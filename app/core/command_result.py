"""Structured result returned by SUS-ADB command runners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None

    @classmethod
    def from_command(
        cls,
        command: Sequence[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        *,
        timed_out: bool = False,
        error: str | None = None,
    ) -> "CommandResult":
        return cls(
            command=tuple(str(part) for part in command),
            returncode=returncode,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            timed_out=timed_out,
            error=error,
        )

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None

    @property
    def output(self) -> str:
        parts = [part for part in (self.stdout, self.stderr, self.error or "") if part]
        return "\n".join(parts)
