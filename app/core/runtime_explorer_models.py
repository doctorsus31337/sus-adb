"""Immutable Runtime Explorer records and structured events."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HookTarget(str, Enum):
    JAVA_METHOD = "java-method"
    NATIVE_EXPORT = "native-export"


class RuntimeEventType(str, Enum):
    DISCOVERY = "discovery"
    METHOD_ENTER = "method-enter"
    METHOD_LEAVE = "method-leave"
    EXCEPTION = "exception"
    NATIVE_ENTER = "native-enter"
    NATIVE_LEAVE = "native-leave"
    STACK = "stack"
    WARNING = "warning"
    ERROR = "error"
    LIFECYCLE = "lifecycle"


@dataclass(frozen=True, slots=True)
class JavaClassRecord:
    class_name: str
    namespace: str = ""
    simple_name: str = ""
    loader_description: str = ""
    classification: str = "class"
    device_serial: str = ""
    target_identifier: str = ""

    def __post_init__(self):
        object.__setattr__(self, "namespace", self.namespace or self.class_name.rpartition(".")[0])
        object.__setattr__(self, "simple_name", self.simple_name or self.class_name.rpartition(".")[2] or self.class_name)

    @property
    def display_label(self): return f"{self.class_name} · {self.classification}"
    def to_dict(self): return asdict(self)


@dataclass(frozen=True, slots=True)
class JavaMethodRecord:
    declaring_class: str
    method_name: str
    overload_index: int
    argument_types: tuple[str, ...] = ()
    return_type: str = "void"
    is_static: bool = False
    is_constructor: bool = False
    is_native: bool = False
    visibility: str = ""
    device_serial: str = ""
    target_identifier: str = ""

    def __post_init__(self): object.__setattr__(self, "argument_types", tuple(self.argument_types))
    @property
    def signature(self): return f"{self.declaring_class}.{self.method_name}({', '.join(self.argument_types)}): {self.return_type}"
    @property
    def display_label(self): return f"[{self.overload_index}] {self.signature}"
    def to_dict(self): return asdict(self)


@dataclass(frozen=True, slots=True)
class JavaFieldRecord:
    declaring_class: str
    field_name: str
    type_name: str = ""
    is_static: bool = False
    visibility: str = ""
    value_preview: str | None = None
    device_serial: str = ""
    target_identifier: str = ""
    @property
    def display_label(self): return f"{self.declaring_class}.{self.field_name}: {self.type_name}"
    def to_dict(self): return asdict(self)


@dataclass(frozen=True, slots=True)
class NativeModuleRecord:
    module_name: str
    path: str
    base_address: str = ""
    size: int = 0
    device_serial: str = ""
    target_identifier: str = ""
    @property
    def display_label(self): return f"{self.module_name} · {self.base_address} · {self.size} bytes\n{self.path}"
    def to_dict(self): return asdict(self)


@dataclass(frozen=True, slots=True)
class NativeSymbolRecord:
    symbol_name: str
    symbol_type: str = "export"
    address: str = ""
    module_name: str = ""
    device_serial: str = ""
    target_identifier: str = ""
    @property
    def display_label(self): return f"{self.module_name}!{self.symbol_name} · {self.address} · {self.symbol_type}"
    def to_dict(self): return asdict(self)


@dataclass(frozen=True, slots=True)
class RuntimeHookSpec:
    target_type: HookTarget
    owner_name: str
    member_name: str
    overload: tuple[str, ...] = ()
    observation_settings: Mapping[str, Any] = field(default_factory=dict)
    modification_settings: Mapping[str, Any] = field(default_factory=dict)
    generated_script_name: str = "runtime-hook"
    changes_runtime: bool = False
    caution: str = "Observation hooks are temporary and unload on request or detach."
    required_scope_category: str = "runtime-inspection"
    selected_target: str = ""
    hook_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "target_type", HookTarget(self.target_type))
        object.__setattr__(self, "overload", tuple(self.overload))
        object.__setattr__(self, "observation_settings", dict(self.observation_settings))
        object.__setattr__(self, "modification_settings", dict(self.modification_settings))
        if self.changes_runtime:
            object.__setattr__(self, "required_scope_category", "state-changing-testing")
            object.__setattr__(self, "caution", "State-changing hook: unload the hook or detach the runtime session to restore behavior.")

    @property
    def classification(self): return "state-changing" if self.changes_runtime else "read-only"
    @property
    def display_label(self): return f"{self.generated_script_name} · {self.owner_name}!{self.member_name} · {self.classification}"
    def to_dict(self):
        data = asdict(self); data["target_type"] = self.target_type.value; return data


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    event_type: RuntimeEventType
    hook_id: str = ""
    owner_name: str = ""
    member_name: str = ""
    thread_id: str | int | None = None
    arguments: tuple[Any, ...] = ()
    return_value: Any = None
    exception: Any = None
    stack_trace: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    raw_message: Any = None
    severity: str = "info"
    device_serial: str = ""
    target_identifier: str = ""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "event_type", RuntimeEventType(self.event_type))
        object.__setattr__(self, "arguments", tuple(self.arguments))
        object.__setattr__(self, "payload", dict(self.payload))

    @property
    def display_text(self):
        target = "!".join(part for part in (self.owner_name, self.member_name) if part)
        return f"[{self.timestamp}] {self.event_type.value.upper()} {target} {self.payload or ''}".rstrip()

    def to_dict(self):
        data = asdict(self); data["event_type"] = self.event_type.value; data["display_text"] = self.display_text; return data
