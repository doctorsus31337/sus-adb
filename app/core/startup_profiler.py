"""Bounded local-only startup stage profiling with sanitized reports."""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass


_LOCAL_PATHS = (
    re.compile(r"/home/[^/\s]+(?:/[^\s]*)?"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+(?:\\[^\s]*)?"),
)


@dataclass(frozen=True, slots=True)
class StartupStage:
    name: str
    start_offset: float
    duration: float
    status: str
    classification: str
    thread: str
    note: str = ""


class StartupProfiler:
    """Records a small, thread-safe history without telemetry or sensitive values."""

    VALID_CLASSIFICATIONS = frozenset(("eager", "deferred", "on-demand"))
    VALID_THREADS = frozenset(("ui", "worker"))

    def __init__(self, *, clock=time.perf_counter, origin=None, max_stages=128):
        self.clock = clock
        self.origin = self.clock() if origin is None else float(origin)
        self._stages: deque[StartupStage] = deque(maxlen=max(1, int(max_stages)))
        self._lock = threading.RLock()
        self.ui_thread_id = threading.get_ident()

    @staticmethod
    def sanitize_note(note) -> str:
        value = " ".join(str(note or "").split())[:240]
        for pattern in _LOCAL_PATHS:
            value = pattern.sub("[LOCAL-PATH-REDACTED]", value)
        return value

    def _thread_kind(self) -> str:
        return "ui" if threading.get_ident() == self.ui_thread_id else "worker"

    def record_interval(
        self,
        name,
        started,
        finished,
        *,
        status="ok",
        classification="eager",
        thread=None,
        note="",
    ) -> StartupStage:
        classification = classification if classification in self.VALID_CLASSIFICATIONS else "eager"
        thread = thread if thread in self.VALID_THREADS else self._thread_kind()
        stage = StartupStage(
            str(name)[:80],
            max(0.0, float(started) - self.origin),
            max(0.0, float(finished) - float(started)),
            str(status)[:32],
            classification,
            thread,
            self.sanitize_note(note),
        )
        with self._lock:
            self._stages.append(stage)
        return stage

    @contextmanager
    def stage(self, name, *, classification="eager", note=""):
        started = self.clock()
        status = "ok"
        final_note = note
        try:
            yield
        except Exception as exc:
            status = "failed"
            final_note = f"{note} {type(exc).__name__}".strip()
            raise
        finally:
            self.record_interval(
                name,
                started,
                self.clock(),
                status=status,
                classification=classification,
                note=final_note,
            )

    def record(self, name, duration=0.0, **kwargs) -> StartupStage:
        finished = self.clock()
        return self.record_interval(name, finished - max(0.0, float(duration)), finished, **kwargs)

    def stages(self) -> tuple[StartupStage, ...]:
        with self._lock:
            return tuple(self._stages)

    def summary(self) -> str:
        lines = ("SUS Companion local startup report", "No telemetry or network reporting is used.", "")
        rows = tuple(
            f"{stage.name:<30} +{stage.start_offset:7.3f}s  {stage.duration:7.3f}s  "
            f"{stage.status:<7} {stage.classification:<9} {stage.thread}"
            + (f"  {stage.note}" if stage.note else "")
            for stage in self.stages()
        )
        return "\n".join((*lines, *rows))
