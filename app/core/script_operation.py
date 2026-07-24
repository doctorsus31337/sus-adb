"""UI-independent Script Studio operation state and error presentation."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScriptBadge(str, Enum):
    UNSAVED = "Unsaved"
    SAVED = "Saved"
    LOADED = "Loaded"
    RELOAD_REQUIRED = "Reload Required"
    UNLOADED = "Unloaded"
    ERROR = "Error"


class OperationState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScriptOperation:
    operation: str = ""
    script: str = ""
    target: str = ""
    device: str = ""
    stage: str = ""
    started_at: str = ""
    state: OperationState = OperationState.IDLE
    message: str = ""
    error_line: int | None = None
    technical_details: str = ""


@dataclass(frozen=True, slots=True)
class ValidationPresentation:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    advisories: tuple[str, ...] = ()


class ScriptOperationModel:
    LINE_PATTERNS = (
        re.compile(r"\bline(?:number)?\s*[:=]?\s*(\d+)\b", re.IGNORECASE),
        re.compile(r"(?:^|[^\d]):(\d+)(?::\d+)?(?:\D|$)"),
    )

    def __init__(self, clock: Callable[[], str] = utc_now):
        self.clock = clock
        self.current = ScriptOperation()
        self.badge = ScriptBadge.SAVED

    @property
    def busy(self) -> bool:
        return self.current.state is OperationState.RUNNING

    def begin(
        self,
        operation: str,
        *,
        script: str = "",
        target: str = "",
        device: str = "",
        stage: str = "Preparing",
    ) -> bool:
        if self.busy:
            return False
        self.current = ScriptOperation(
            operation,
            script,
            target,
            device,
            stage,
            self.clock(),
            OperationState.RUNNING,
            f"{operation}…",
        )
        return True

    def set_stage(self, stage: str) -> None:
        if self.busy:
            self.current = replace(self.current, stage=stage)

    def succeed(self, message: str, badge: ScriptBadge | None = None) -> None:
        self.current = replace(
            self.current,
            state=OperationState.SUCCESS,
            stage="Complete",
            message=message,
            error_line=None,
            technical_details="",
        )
        if badge is not None:
            self.badge = badge

    def fail(
        self,
        error: str,
        *,
        technical_details: str = "",
        line: int | None = None,
    ) -> None:
        details = technical_details or error
        self.current = replace(
            self.current,
            state=OperationState.ERROR,
            stage="Failed",
            message=error or "Operation failed.",
            error_line=line or self.parse_source_line(details),
            technical_details=details,
        )
        self.badge = ScriptBadge.ERROR

    def edited(self, loaded: bool) -> None:
        self.badge = (
            ScriptBadge.RELOAD_REQUIRED if loaded else ScriptBadge.UNSAVED
        )

    def saved(self, loaded: bool) -> None:
        self.badge = (
            ScriptBadge.RELOAD_REQUIRED if loaded else ScriptBadge.SAVED
        )

    def loaded(self) -> None:
        self.badge = ScriptBadge.LOADED

    def unloaded(self) -> None:
        self.badge = ScriptBadge.UNLOADED

    @classmethod
    def parse_source_line(cls, text: str) -> int | None:
        for pattern in cls.LINE_PATTERNS:
            match = pattern.search(text or "")
            if match:
                value = int(match.group(1))
                return value if value > 0 else None
        return None

    @staticmethod
    def present_validation(result, *, show_advisories: bool) -> ValidationPresentation:
        return ValidationPresentation(
            tuple(result.errors),
            tuple(result.warnings),
            tuple(getattr(result, "suggestions", ())),
            tuple(getattr(result, "advisories", ())) if show_advisories else (),
        )

    @staticmethod
    def load_guidance(already_loaded: bool, edited: bool = False) -> str:
        if already_loaded and edited:
            return "This script is already loaded and has changed. Use Reload to apply the saved source."
        if already_loaded:
            return "This script is already loaded. Use Reload after editing its saved source."
        return "Load compiles and adds the selected script to the active runtime session."
