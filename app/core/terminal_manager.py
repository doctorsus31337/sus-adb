"""Integrated terminal command execution and history."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable

from app.core.command_registry import CommandRegistry
from app.core.command_router import CommandClassification,CommandRoute,CommandRouter
from app.core.command_runner import CommandRunner
from app.core.history_manager import HistoryManager
from app.core.host_tool_resolver import HostToolResolver


class TerminalManager:
    PROMPT = "sus-companion > "

    def __init__(
        self,
        log_callback: Callable[[str], None],
        clear_callback: Callable[[], None] | None = None,
        resolver: HostToolResolver | None = None,
        router: CommandRouter | None = None,
        interactive_callback=None,
    ):
        self.log = log_callback
        self.clear_callback = clear_callback
        self.history = HistoryManager()
        self.runner = CommandRunner()
        self.resolver = resolver or HostToolResolver()
        self.router = router or CommandRouter(self.resolver)
        self.interactive_callback = interactive_callback
        self.cwd = os.getcwd()
        self._active_lock = threading.Lock()
        self._active = False

    def execute(self, command: str) -> None:
        command = command.strip()
        if not command:
            return

        lowered = command.casefold()

        if lowered in {"clear", "cls"}:
            self.history.add(command)
            if self.clear_callback is not None:
                self.clear_callback()
            return

        if lowered == "help":
            self.history.add(command)
            self.log(CommandRegistry.render_text())
            return

        if lowered == "stop":
            self.history.add(command)
            self.log("[INFO] Process cancellation will be added in the next backend milestone.")
            return

        if lowered.startswith("cd "):
            self.history.add(command)
            self._change_directory(command[3:].strip())
            return

        route = self.router.classify(command)
        if route.classification in {CommandClassification.UNSUPPORTED,CommandClassification.AMBIGUOUS}:
            self.log(f"[ERROR] {route.reason}")
            return
        self.history.add(command)
        if route.classification is CommandClassification.INTERACTIVE:
            if self.interactive_callback is not None:
                self.interactive_callback(route)
            else:
                self.log("This command opens an interactive session. Use Sessions Center.")
            return

        with self._active_lock:
            if self._active:
                self.log("[BUSY] Wait for the current command to finish.")
                return
            self._active = True

        threading.Thread(target=self._run, args=(route,), daemon=True).start()

    def _run(self, command: str | CommandRoute) -> None:
        route = (
            command if isinstance(command, CommandRoute)
            else self.router.classify(command)
        )
        command_text = route.raw
        self.log(f"\n{self.PROMPT}{command_text}\n")
        try:
            argv = route.resolved_argv
            if not argv:
                return
            name = self.router._name(route.argv[0])
            resolved = self.resolver.resolve(name)
            if resolved:
                argv = (resolved, *route.argv[1:])
            elif (
                name in self.router.registry_executables
                or name in {"adb", "fastboot", "frida", "frida-ps", "frida-trace", "objection"}
            ):
                self.log(f"[ERROR] {self.resolver.missing_message(name)}")
                return
            returncode = self.runner.stream(argv, self._write_line, cwd=self.cwd)
            self.log("")
            self.log("[✓] Complete" if returncode == 0 else f"[✗] Exit code {returncode}")
            self.log("")
        except OSError as exc:
            self.log(f"[ERROR] {exc}")
        finally:
            with self._active_lock:
                self._active = False

    def _write_line(self, line: str) -> None:
        if line:
            self.log(line)

    def _change_directory(self, raw_path: str) -> None:
        path = os.path.abspath(os.path.expanduser(raw_path.strip('"')))
        if not os.path.isdir(path):
            self.log(f"[ERROR] Directory not found: {path}")
            return
        self.cwd = path
        self.log(f"[CWD] {self.cwd}")
