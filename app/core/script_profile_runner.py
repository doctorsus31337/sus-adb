"""Visible, ordered, cancellable Script Studio profile execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from app.core.frida_runtime_manager import FridaRuntimeManager, RuntimeResult
from app.core.script_descriptor import ScriptDescriptor, TrustState
from app.core.script_event import ScriptEvent, ScriptEventType
from app.core.script_profile import FailurePolicy, ScriptProfile


@dataclass(frozen=True, slots=True)
class ProfileRunResult:
    ok: bool
    stages: tuple[tuple[str, str], ...] = ()
    errors: tuple[str, ...] = ()


class ScriptProfileRunner:
    def __init__(self, runtime: FridaRuntimeManager, event_callback: Callable[[ScriptEvent], None] | None = None):
        self.runtime, self.event_callback = runtime, event_callback
        self.cancelled = False
        self.loaded_ids: list[str] = []

    def validate(self, profile: ScriptProfile, scripts: Mapping[str, ScriptDescriptor], *, confirm_untrusted=False, confirm_state_change=False) -> ProfileRunResult:
        errors = []
        for stage in profile.stages:
            if not stage.enabled: continue
            descriptor = scripts.get(stage.script_id)
            if descriptor is None: errors.append(f"Missing script: {stage.script_id}"); continue
            if descriptor.trust is TrustState.UNTRUSTED and not confirm_untrusted: errors.append(f"Untrusted confirmation required: {descriptor.name}")
            if descriptor.changes_runtime and not confirm_state_change: errors.append(f"State-change confirmation required: {descriptor.name}")
            if stage.requires_confirmation and not (confirm_untrusted or confirm_state_change): errors.append(f"Stage confirmation required: {descriptor.name}")
        return ProfileRunResult(not errors, errors=tuple(errors))

    def run(self, profile: ScriptProfile, scripts: Mapping[str, ScriptDescriptor], *, confirm_untrusted=False, confirm_state_change=False, delay: Callable[[float], None] | None = None) -> ProfileRunResult:
        valid = self.validate(profile, scripts, confirm_untrusted=confirm_untrusted, confirm_state_change=confirm_state_change)
        if not valid.ok: return valid
        self.cancelled = False; states = []; errors = []
        for stage in profile.stages:
            if not stage.enabled: states.append((stage.script_id, "stopped")); continue
            if self.cancelled: states.append((stage.script_id, "stopped")); break
            descriptor = scripts[stage.script_id]
            self._emit(descriptor, "loading")
            result = self.runtime.load_script(descriptor, confirm_untrusted=confirm_untrusted, confirm_state_change=confirm_state_change)
            if result.ok:
                states.append((stage.script_id, "active")); self.loaded_ids.append(stage.script_id); self._emit(descriptor, "active")
            else:
                states.append((stage.script_id, "failed")); errors.append(result.error or "Stage failed."); self._emit(descriptor, "failed")
                if stage.failure_policy is FailurePolicy.STOP: break
            if delay and stage.delay_seconds: delay(stage.delay_seconds)
        return ProfileRunResult(not errors, tuple(states), tuple(errors))

    def cancel(self): self.cancelled = True

    def unload(self) -> tuple[RuntimeResult, ...]:
        results = tuple(self.runtime.unload_script(script_id) for script_id in tuple(self.loaded_ids))
        self.loaded_ids.clear(); return results

    def _emit(self, descriptor, state):
        if self.event_callback:
            self.event_callback(ScriptEvent(ScriptEventType.LIFECYCLE, f"Profile stage {state}.", script_id=descriptor.script_id, script_name=descriptor.name, payload={"stage_state": state}))
