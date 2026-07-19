"""GUI-independent, ownership-aware plugin contribution registry."""
from dataclasses import dataclass,field
from typing import Any,Callable,Mapping
@dataclass(frozen=True,slots=True)
class Contribution:
    contribution_id:str;contribution_type:str;title:str;plugin_id:str="";factory:Callable|None=None;metadata:Mapping[str,Any]=field(default_factory=dict);scope_requirement:str="";capability_requirement:str="";classification:str="read-only";preview_callback:Callable|None=None;confirmation_required:bool=False;execution_callback:Callable|None=None;rollback_guidance:str=""
    def __post_init__(self):object.__setattr__(self,"metadata",dict(self.metadata))
class ContributionRegistry:
    def __init__(self):self._items={}
    def register(self,plugin_id,contributions):
        added=[]
        try:
            for c in contributions:
                item=c if c.plugin_id==plugin_id else Contribution(**{**c.__dict__,"plugin_id":plugin_id}) if hasattr(c,"__dict__") else Contribution(c.contribution_id,c.contribution_type,c.title,plugin_id,c.factory,c.metadata,c.scope_requirement,c.capability_requirement,c.classification,c.preview_callback,c.confirmation_required,c.execution_callback,c.rollback_guidance)
                if item.contribution_id in self._items:raise ValueError(f"Duplicate contribution ID: {item.contribution_id}")
                self._items[item.contribution_id]=item;added.append(item.contribution_id)
            return tuple(self._items[i] for i in added)
        except Exception:
            for i in added:self._items.pop(i,None)
            raise
    def unregister_plugin(self,plugin_id):
        removed=tuple(v for v in self._items.values() if v.plugin_id==plugin_id)
        for v in removed:self._items.pop(v.contribution_id,None)
        return removed
    def list(self,contribution_type=None):return tuple(sorted((v for v in self._items.values() if not contribution_type or v.contribution_type==contribution_type),key=lambda v:(v.contribution_type,v.contribution_id)))
    def by_plugin(self,plugin_id):return tuple(v for v in self.list() if v.plugin_id==plugin_id)
