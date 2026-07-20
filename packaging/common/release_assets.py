"""Deterministic selection and reporting for optional curated script assets."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from pathlib import Path

CATEGORIES = ("frida", "metadata", "objection", "profiles")
PRIVATE_DRAFTS = frozenset((
    "scripts/frida/custom/flutter_popup_bypass.js",
    "scripts/metadata/flutter_popup_bypass.meta.json",
))
BLOCKED_PARTS = frozenset(("__pycache__", ".git", ".pytest_cache"))
BLOCKED_SUFFIXES = (".pyc", ".pyo")


def tracked_script_paths(root: Path) -> tuple[str, ...]:
    """Return Git-approved paths, or archive paths when .git is unavailable."""
    root = Path(root).resolve()
    if (root / ".git").exists():
        output = subprocess.check_output(
            ("git", "ls-files", "-z", "--", *(f"scripts/{name}" for name in CATEGORIES)),
            cwd=root,
        )
        return tuple(item for item in output.decode("utf-8").split("\0") if item)
    return tuple(
        item.relative_to(root).as_posix()
        for name in CATEGORIES
        for item in sorted((root / "scripts" / name).rglob("*"))
        if item.is_file()
    )


def select_curated_assets(
    root: Path, tracked_paths: Iterable[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    root = Path(root).resolve()
    selected = {name: [] for name in CATEGORIES}
    candidates = tracked_script_paths(root) if tracked_paths is None else tuple(tracked_paths)
    for raw in sorted(set(candidates)):
        relative = Path(raw)
        normalized = relative.as_posix()
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Curated asset path must be repository-relative: {raw}")
        if normalized in PRIVATE_DRAFTS:
            continue
        if any(part in BLOCKED_PARTS for part in relative.parts) or normalized.casefold().endswith(BLOCKED_SUFFIXES):
            continue
        if len(relative.parts) < 3 or relative.parts[0] != "scripts" or relative.parts[1] not in CATEGORIES:
            continue
        source = root / relative
        if source.is_file():
            selected[relative.parts[1]].append(normalized)
    return {name: tuple(paths) for name, paths in selected.items()}


def asset_report(selected: dict[str, tuple[str, ...]]) -> dict:
    categories = {
        name: {"count": len(selected.get(name, ())), "paths": list(selected.get(name, ()))}
        for name in CATEGORIES
    }
    return {
        "format": 1,
        "core_curated_script_studio_assets": {
            "count": sum(value["count"] for value in categories.values()),
            "categories": categories,
        },
        "user_local_script_studio_assets": {"count": 0, "packaged": False},
    }


def write_asset_report(path: Path, selected: dict[str, tuple[str, ...]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asset_report(selected), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
