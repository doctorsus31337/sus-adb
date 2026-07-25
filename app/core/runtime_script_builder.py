"""Safe deterministic Runtime Explorer hook generation."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from app.core import runtime_agent_templates as templates
from app.core.runtime_explorer_models import HookTarget, RuntimeHookSpec
from app.core.script_descriptor import ScriptDescriptor, ScriptKind, TrustState


@dataclass(frozen=True, slots=True)
class ScriptBuildResult:
    ok: bool
    source: str = ""
    filename: str = ""
    descriptor: ScriptDescriptor | None = None
    error: str | None = None


class RuntimeScriptBuilder:
    JAVA_NAME = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$")
    MEMBER = re.compile(r"^[A-Za-z_$<>][\w$<>]*$")
    TEST_EXCEPTIONS = {"java.lang.IllegalStateException", "java.lang.IllegalArgumentException", "java.lang.SecurityException", "java.lang.RuntimeException"}

    @staticmethod
    def _safe_value(value):
        if isinstance(value, float) and not math.isfinite(value): raise ValueError("Replacement numbers must be finite.")
        if value is None or isinstance(value, (str, bool, int, float)): return value
        if isinstance(value, list): return [RuntimeScriptBuilder._safe_value(item) for item in value]
        if isinstance(value, dict) and all(isinstance(key, str) for key in value): return {key: RuntimeScriptBuilder._safe_value(item) for key, item in value.items()}
        raise ValueError("Replacement values must be JSON-compatible primitives, arrays, or string-keyed objects.")

    def build(self, spec: RuntimeHookSpec) -> ScriptBuildResult:
        if not spec.selected_target: return ScriptBuildResult(False, error="An explicitly selected target is required.")
        if not spec.owner_name or not spec.member_name: return ScriptBuildResult(False, error="A class/module and method/symbol are required.")
        if spec.target_type is HookTarget.JAVA_METHOD:
            if not self.JAVA_NAME.fullmatch(spec.owner_name) or not self.MEMBER.fullmatch(spec.member_name): return ScriptBuildResult(False, error="Invalid Java class or method name.")
            if not spec.overload: return ScriptBuildResult(False, error="Select an explicit Java overload before generating a hook.")
        elif any(char in spec.owner_name + spec.member_name for char in "\0\r\n"):
            return ScriptBuildResult(False, error="Invalid native module or symbol name.")
        observation = {"logArguments": True, "logReturn": True, "logExceptions": True, "javaStack": False, "nativeBacktrace": False, "rateLimit": 0, "maxPreview": 512, **spec.observation_settings}
        try:
            observation["rateLimit"] = max(0, int(observation["rateLimit"]))
            observation["maxPreview"] = min(16384, max(32, int(observation["maxPreview"])))
        except (TypeError, ValueError): return ScriptBuildResult(False, error="Rate limit and preview length must be integers.")
        modification = dict(spec.modification_settings)
        if modification:
            mode = modification.get("mode")
            if spec.target_type is not HookTarget.JAVA_METHOD or mode not in {"replace-argument", "replace-return", "throw-exception"}: return ScriptBuildResult(False, error="Only explicit Java argument, return replacement, or supported test exceptions are supported.")
            if mode == "throw-exception":
                if modification.get("exceptionClass") not in self.TEST_EXCEPTIONS:return ScriptBuildResult(False,error="Select a supported Java test exception class.")
                modification["message"] = str(modification.get("message", "SUS Companion authorized test exception"))[:512]
            else:
                try: modification["value"] = self._safe_value(modification.get("value"))
                except ValueError as exc: return ScriptBuildResult(False, error=str(exc))
            if mode == "replace-argument":
                try: modification["argumentIndex"] = int(modification.get("argumentIndex"))
                except (TypeError, ValueError): return ScriptBuildResult(False, error="A valid argument index is required.")
                if modification["argumentIndex"] < 0 or modification["argumentIndex"] >= len(spec.overload): return ScriptBuildResult(False, error="The argument index is outside the selected overload.")
        if bool(modification) != spec.changes_runtime: return ScriptBuildResult(False, error="Hook classification does not match its modification settings.")
        canonical = json.dumps({"targetType": spec.target_type.value, "owner": spec.owner_name, "member": spec.member_name, "overload": spec.overload, "observation": observation, "modification": modification, "target": spec.selected_target}, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", spec.generated_script_name).strip(".-") or "runtime-hook"
        filename = f"{stem}-{digest[:12]}.js"
        metadata = {"hookId": spec.hook_id, "target": spec.selected_target, "classification": spec.classification, "specDigest": digest}
        source = templates.java_observation(metadata, spec.owner_name, spec.member_name, spec.overload, observation, modification) if spec.target_type is HookTarget.JAVA_METHOD else templates.native_observation(metadata, spec.owner_name, spec.member_name, observation)
        descriptor = ScriptDescriptor(f"runtime-{digest[:20]}", Path(filename).stem, ScriptKind.FRIDA, f"frida/generated/{filename}", description=f"Runtime Explorer hook for {spec.owner_name}!{spec.member_name}", source="SUS Companion Runtime Explorer", tags=("runtime-explorer", spec.classification), target_requirements=(spec.selected_target,), runtime_requirements=("frida",), changes_runtime=spec.changes_runtime, trust=TrustState.TRUSTED_LOCAL, sha256=hashlib.sha256(source.encode()).hexdigest(), caution=spec.caution, parameters={"hook_id": spec.hook_id, "required_scope": spec.required_scope_category}, metadata_path=f"metadata/{Path(filename).stem}.meta.json")
        return ScriptBuildResult(True, source, filename, descriptor)
