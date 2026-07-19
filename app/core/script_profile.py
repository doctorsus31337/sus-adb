"""Immutable declarative Script Studio profiles and stages."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class FailurePolicy(str, Enum):
    CONTINUE = "continue"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class ScriptStage:
    script_id: str
    enabled: bool = True
    parameters: Mapping[str, Any] = field(default_factory=dict)
    failure_policy: FailurePolicy = FailurePolicy.STOP
    delay_seconds: float = 0
    requires_confirmation: bool = False

    def __post_init__(self):
        object.__setattr__(self, "failure_policy", FailurePolicy(self.failure_policy))
        object.__setattr__(self, "parameters", dict(self.parameters))
        if self.delay_seconds < 0:
            raise ValueError("Profile stage delays cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScriptProfile:
    name: str
    description: str = ""
    target_requirement: str = ""
    stages: tuple[ScriptStage, ...] = ()
    version: int = 1
    digest: str = ""

    def __post_init__(self):
        object.__setattr__(self, "stages", tuple(stage if isinstance(stage, ScriptStage) else ScriptStage(**stage) for stage in self.stages))
        if not self.digest:
            payload = json.dumps({"name": self.name, "description": self.description, "target_requirement": self.target_requirement, "stages": [asdict(stage) for stage in self.stages], "version": self.version}, sort_keys=True, default=lambda item: item.value)
            object.__setattr__(self, "digest", hashlib.sha256(payload.encode()).hexdigest())

    def to_dict(self):
        return {"name": self.name, "description": self.description, "target_requirement": self.target_requirement, "stages": [{**asdict(stage), "failure_policy": stage.failure_policy.value} for stage in self.stages], "version": self.version, "digest": self.digest}

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"], description=data.get("description", ""),
            target_requirement=data.get("target_requirement", ""),
            stages=tuple(ScriptStage(**stage) for stage in data.get("stages", ())),
            version=data.get("version", 1), digest=data.get("digest", ""),
        )
