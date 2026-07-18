"""Safe subprocess helpers shared by the SUS-ADB backend."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Sequence

from app.core.command_result import CommandResult


class CommandRunner:
    def run(
        self,
        command: Sequence[str],
        *,
        timeout: float = 30,
        cwd: str | None = None,
    ) -> CommandResult:
        args = [str(part) for part in command]

        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=cwd,
                creationflags=self._creation_flags(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._coerce_text(exc.stdout)
            stderr = self._coerce_text(exc.stderr)
            return CommandResult.from_command(
                args,
                -1,
                stdout,
                stderr,
                timed_out=True,
                error=f"Command timed out after {timeout:g} seconds.",
            )
        except OSError as exc:
            return CommandResult.from_command(args, -1, error=str(exc))

        return CommandResult.from_command(
            args,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    def stream_shell(
        self,
        command: str,
        on_line: Callable[[str], None],
        *,
        cwd: str | None = None,
    ) -> int:
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=self._creation_flags(),
        )

        if process.stdout is not None:
            for line in iter(process.stdout.readline, ""):
                on_line(line.rstrip("\r\n"))

        return process.wait()

    @staticmethod
    def _coerce_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    @staticmethod
    def _creation_flags() -> int:
        if os.name == "nt":
            return getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return 0
