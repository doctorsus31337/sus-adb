"""Serializable, immutable Script Studio library descriptors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class ScriptKind(str, Enum):
    FRIDA = "frida"
    OBJECTION_RECIPE = "objection-recipe"
    PROFILE = "profile"


class TrustState(str, Enum):
    BUILT_IN = "built-in"
    TRUSTED_LOCAL = "trusted-local"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class DescriptorValidation:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ScriptDescriptor:
    script_id: str
    name: str
    kind: ScriptKind
    path: str
    description: str = ""
    author: str = ""
    source: str = ""
    tags: tuple[str, ...] = ()
    target_requirements: tuple[str, ...] = ()
    runtime_requirements: tuple[str, ...] = ()
    changes_runtime: bool = False
    trust: TrustState = TrustState.UNTRUSTED
    enabled: bool = True
    sha256: str = ""
    created_at: str = field(default_factory=utc_now)
    modified_at: str = field(default_factory=utc_now)
    caution: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    metadata_path: str = ""

    def __post_init__(self):
        object.__setattr__(self, "script_id", self.script_id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "kind", ScriptKind(self.kind))
        object.__setattr__(self, "trust", TrustState(self.trust))
        object.__setattr__(self, "path", str(Path(self.path).expanduser()))
        object.__setattr__(self, "metadata_path", str(Path(self.metadata_path).expanduser()) if self.metadata_path else "")
        object.__setattr__(self, "tags", tuple(dict.fromkeys(str(tag).strip() for tag in self.tags if str(tag).strip())))
        object.__setattr__(self, "target_requirements", tuple(self.target_requirements))
        object.__setattr__(self, "runtime_requirements", tuple(self.runtime_requirements))
        object.__setattr__(self, "parameters", dict(self.parameters))

    @property
    def classification(self) -> str:
        return "state-changing" if self.changes_runtime else "read-only"

    def validate(self) -> DescriptorValidation:
        errors = []
        if not self.script_id or any(char in self.script_id for char in "/\\\0"):
            errors.append("A stable script ID without path separators is required.")
        if not self.name:
            errors.append("A script name is required.")
        if not self.path:
            errors.append("A script path is required.")
        if self.sha256 and (len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256.casefold())):
            errors.append("The SHA-256 digest is invalid.")
        return DescriptorValidation(not errors, tuple(errors))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["trust"] = self.trust.value
        data["tags"] = list(self.tags)
        data["target_requirements"] = list(self.target_requirements)
        data["runtime_requirements"] = list(self.runtime_requirements)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScriptDescriptor":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in data.items() if key in allowed})
