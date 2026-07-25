"""Immutable authorization scope for an Android assessment."""
from __future__ import annotations
import hashlib, json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Mapping

ACTION_CATEGORIES = ("recon","runtime-inspection","script-execution","network-analysis","storage-inspection","apk-analysis","evidence-collection","state-changing-testing","destructive-testing","authentication-testing","repeated-input-testing","sensitive-data-inspection","instrumentation-resilience-testing")
HIGH_IMPACT_CATEGORIES = ("state-changing-testing","destructive-testing","authentication-testing","repeated-input-testing","sensitive-data-inspection","network-analysis")
def now(): return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True, slots=True)
class ScopeValidation:
    valid: bool; errors: tuple[str,...]=(); warnings: tuple[str,...]=()

@dataclass(frozen=True, slots=True)
class AssessmentScope:
    scope_id: str; case_name: str; description: str=""; tester_name: str=""; client_project: str=""; authorization_reference: str=""; authorization_confirmed: bool=False
    device_serial: str=""; device_model: str=""; target_name: str=""; package_identifier: str=""; pid: int|None=None
    allowed_actions: tuple[str,...]=(); excluded_actions: tuple[str,...]=(); start_date: str=""; end_date: str|None=None; notes: str=""; created_at: str=field(default_factory=now); modified_at: str=field(default_factory=now)
    def __post_init__(self):
        object.__setattr__(self,"allowed_actions",tuple(dict.fromkeys(self.allowed_actions))); object.__setattr__(self,"excluded_actions",tuple(dict.fromkeys(self.excluded_actions)))
    def validate(self, *, for_start=False):
        errors=[]
        if not self.scope_id.strip(): errors.append("A scope ID is required.")
        if not self.case_name.strip(): errors.append("An assessment name is required.")
        if not self.device_serial.strip(): errors.append("An explicitly selected device is required.")
        if not (self.package_identifier or self.target_name): errors.append("An explicitly selected target is required.")
        if for_start and not self.authorization_confirmed: errors.append("Explicit authorization confirmation is required.")
        try:
            start=date.fromisoformat(self.start_date) if self.start_date else date.today(); end=date.fromisoformat(self.end_date) if self.end_date else None
            if end and end < start: errors.append("The scope end date precedes its start date.")
        except ValueError: errors.append("Scope dates must use YYYY-MM-DD.")
        invalid=(set(self.allowed_actions)|set(self.excluded_actions))-set(ACTION_CATEGORIES)
        if invalid: errors.append("Unsupported action categories: "+", ".join(sorted(invalid)))
        return ScopeValidation(not errors,tuple(errors))
    def allows(self, category, *, on_date=None):
        today=on_date or date.today()
        try:
            start=date.fromisoformat(self.start_date) if self.start_date else date.min; end=date.fromisoformat(self.end_date) if self.end_date else date.max
        except ValueError: return False
        return self.authorization_confirmed and category in self.allowed_actions and category not in self.excluded_actions and start <= today <= end
    @property
    def display_summary(self): return f"{self.case_name} — {self.package_identifier or self.target_name} on {self.device_serial} — {'Authorized' if self.authorization_confirmed else 'Authorization unconfirmed'}"
    @property
    def digest(self):
        data=self.to_dict(); data.pop("modified_at",None); return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls,data:Mapping[str,Any]): return cls(**{k:v for k,v in data.items() if k in cls.__dataclass_fields__})
