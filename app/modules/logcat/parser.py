"""Deterministic parser for Android ``logcat -v threadtime`` output."""

from __future__ import annotations

import re

from app.modules.logcat.models import MAX_RAW_LINE, LogcatPriority, LogcatRecord


_THREADTIME = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)"
    r"\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<priority>[VDIWEF])\s+(?P<tag>.*?):\s?(?P<message>.*)$"
)
_ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)?)"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_STACK_LIKE = re.compile(
    r"^\s+|^(?:at\s+|Caused by:|Suppressed:|\.\.\. \d+ more$)"
)


class ThreadtimeParser:
    """Parse one bounded source line without interpreting its content."""

    @staticmethod
    def decode(value: str | bytes) -> str:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        text = str(value).rstrip("\r\n")
        text = _ANSI.sub("", text)
        text = _CONTROL.sub("\N{REPLACEMENT CHARACTER}", text)
        return text[:MAX_RAW_LINE]

    def parse(
        self,
        value: str | bytes,
        sequence: int,
        previous: LogcatRecord | None = None,
    ) -> LogcatRecord:
        decoded = self.decode(value)
        truncated = len(
            value.decode("utf-8", errors="replace") if isinstance(value, bytes)
            else str(value).rstrip("\r\n")
        ) > MAX_RAW_LINE
        match = _THREADTIME.fullmatch(decoded)
        if match:
            return LogcatRecord(
                sequence=sequence,
                device_timestamp=match.group("timestamp"),
                pid=int(match.group("pid")),
                tid=int(match.group("tid")),
                priority=LogcatPriority(match.group("priority")),
                tag=match.group("tag").strip(),
                message=match.group("message"),
                raw_line=decoded,
                parse_status="parsed-truncated" if truncated else "parsed",
            )
        if decoded and previous is not None and _STACK_LIKE.search(decoded):
            return LogcatRecord(
                sequence=sequence,
                pid=previous.pid,
                tid=previous.tid,
                priority=previous.priority,
                tag=previous.tag,
                message=decoded.lstrip(),
                raw_line=decoded,
                parse_status="continuation",
                continuation_of=previous.sequence,
            )
        return LogcatRecord(
            sequence=sequence,
            message=decoded,
            raw_line=decoded,
            parse_status="blank" if not decoded else (
                "malformed-truncated" if truncated else "malformed"
            ),
        )
