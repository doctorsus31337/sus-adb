"""Central immutable product and build metadata."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path


UNKNOWN = "unknown"


def _build_info(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        key: str(value[key]).strip()
        for key in ("commit", "ref", "timestamp", "channel")
        if value.get(key)
    }


def _source_repository_info(root: Path) -> dict[str, str]:
    """Read local Git identity without launching a process during startup."""
    git_dir = root / ".git"
    if git_dir.is_file():
        try:
            marker = git_dir.read_text(encoding="utf-8").strip()
            if marker.startswith("gitdir:"):
                candidate = Path(marker.split(":", 1)[1].strip())
                git_dir = (
                    candidate if candidate.is_absolute()
                    else (root / candidate).resolve()
                )
        except OSError:
            return {}
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not head.startswith("ref:"):
        return {"commit": head} if head else {}
    reference = head.split(":", 1)[1].strip()
    try:
        commit = (git_dir / reference).read_text(encoding="utf-8").strip()
    except OSError:
        commit = ""
        try:
            for line in (git_dir / "packed-refs").read_text(
                encoding="utf-8"
            ).splitlines():
                if line and not line.startswith(("#", "^")):
                    value, name = line.split(" ", 1)
                    if name == reference:
                        commit = value
                        break
        except (OSError, ValueError):
            pass
    prefix = "refs/heads/"
    return {
        "commit": commit or UNKNOWN,
        "ref": (
            reference[len(prefix):]
            if reference.startswith(prefix) else reference
        ),
    }


@dataclass(frozen=True, slots=True)
class AppMetadata:
    application_name: str = "SUS Companion"
    display_mark: str = "SUS COMPANION"
    descriptor: str = "Android Security & Recovery Workstation"
    legacy_application_name: str = "SUS-ADB Companion"
    preferred_executable: str = "sus-companion"
    legacy_executable: str = "sus-adb"
    version: str = "1.0.0-rc.1"
    release_channel: str = "rc"
    build_channel: str = "source"
    build_identifier: str = "rc1"
    repository_revision: str = UNKNOWN
    repository_ref: str = UNKNOWN
    build_timestamp: str = UNKNOWN
    python_version: str = platform.python_version()
    platform_name: str = platform.system()
    architecture: str = platform.machine()
    plugin_api_version: str = "1.0"
    configuration_schema_version: int = 4
    case_workspace_schema_version: int = 1

    @property
    def display_version(self):
        return (
            f"{self.application_name} {self.version} "
            f"({self.release_channel})"
        )

    @property
    def short_revision(self):
        return (
            self.repository_revision[:12]
            if self.repository_revision != UNKNOWN else UNKNOWN
        )

    @property
    def build_details(self):
        return (
            f"Product version: {self.version}\n"
            f"Commit: {self.short_revision}\n"
            f"Branch/ref: {self.repository_ref}\n"
            f"Build timestamp: {self.build_timestamp}\n"
            f"Build channel: {self.build_channel}"
        )

    @classmethod
    def current(
        cls, version_file=None, build_info_file=None, environ=None
    ):
        env = dict(os.environ if environ is None else environ)
        version_path = Path(
            version_file
            or Path(__file__).resolve().parents[2] / "VERSION"
        )
        try:
            version = version_path.read_text(encoding="utf-8").strip()
        except OSError:
            version = "1.0.0-rc.1"
        info_path = Path(
            build_info_file or version_path.with_name("build-info.json")
        )
        info = _build_info(info_path)
        source_info = (
            _source_repository_info(version_path.parent) if not info else {}
        )
        return cls(
            version=version,
            build_identifier=env.get("SUS_ADB_BUILD_ID", "rc1"),
            repository_revision=env.get(
                "SUS_ADB_REVISION",
                info.get("commit", source_info.get("commit", UNKNOWN)),
            ),
            repository_ref=env.get(
                "SUS_ADB_REF",
                info.get("ref", source_info.get("ref", UNKNOWN)),
            ),
            build_timestamp=env.get(
                "SUS_ADB_BUILD_TIMESTAMP",
                info.get("timestamp", UNKNOWN),
            ),
            build_channel=env.get(
                "SUS_ADB_BUILD_CHANNEL",
                info.get("channel", "source"),
            ),
            python_version=platform.python_version(),
            platform_name=platform.system(),
            architecture=platform.machine(),
        )


METADATA = AppMetadata.current()


def create_metadata(**values):
    """Create deterministic metadata for builds and tests without probing Git."""
    return AppMetadata(**values)
