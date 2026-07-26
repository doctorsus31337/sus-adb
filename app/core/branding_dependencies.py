"""Narrow, once-only guidance for an unavailable Pillow dependency."""

from __future__ import annotations

import sys
import threading


PILLOW_UPDATE_COMMAND = (
    "python -m pip install -r requirements.txt -c constraints.txt"
)
OPTIONAL_PILLOW_MESSAGE = (
    "Optional visual branding is unavailable because Pillow is not installed.\n"
    "Update this environment with:\n"
    f"{PILLOW_UPDATE_COMMAND}"
)
GUI_PILLOW_MESSAGE = (
    "SUS Companion cannot start its CustomTkinter interface because Pillow "
    "is not installed.\nUpdate this environment with:\n"
    f"{PILLOW_UPDATE_COMMAND}"
)

_notice_lock = threading.Lock()
_notice_emitted = False


def is_missing_pillow_error(error: BaseException) -> bool:
    return (
        isinstance(error, ModuleNotFoundError)
        and (
            getattr(error, "name", "") == "PIL"
            or str(getattr(error, "name", "")).startswith("PIL.")
        )
    )


def report_missing_pillow(*, gui_required=False, stream=None) -> bool:
    global _notice_emitted
    with _notice_lock:
        if _notice_emitted:
            return False
        _notice_emitted = True
    target = stream if stream is not None else sys.stderr
    print(
        GUI_PILLOW_MESSAGE if gui_required else OPTIONAL_PILLOW_MESSAGE,
        file=target,
    )
    return True


def _reset_notice_for_tests() -> None:
    global _notice_emitted
    with _notice_lock:
        _notice_emitted = False
