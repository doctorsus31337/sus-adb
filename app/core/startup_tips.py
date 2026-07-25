"""Validated local startup-tip catalog; never reads from the network."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


FALLBACK_TIPS = (
    "Official addons remain inactive until explicitly installed and enabled.",
    "Bootloader unlocking commonly wipes user data and is not a recovery method.",
    "SUS Companion keeps assessment data local and includes no automatic upload.",
)


@dataclass(frozen=True, slots=True)
class StartupTipCatalog:
    tips: tuple[str, ...]
    warning: str = ""

    def select(self, index=0) -> str:
        return self.tips[int(index) % len(self.tips)]


def default_tip_path() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "startup_tips.json"


def load_startup_tips(path=None, *, maximum=24) -> StartupTipCatalog:
    try:
        data = json.loads(Path(path or default_tip_path()).read_text(encoding="utf-8"))
        values = data.get("tips") if isinstance(data, dict) else None
        if not isinstance(values, list):
            raise ValueError("tips must be a list")
        tips = tuple(
            " ".join(value.split())
            for value in values[: max(1, int(maximum))]
            if isinstance(value, str) and 20 <= len(" ".join(value.split())) <= 220
        )
        if not tips:
            raise ValueError("no valid local tips")
        return StartupTipCatalog(tips)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return StartupTipCatalog(FALLBACK_TIPS, f"Local tip catalog fallback: {type(exc).__name__}")
