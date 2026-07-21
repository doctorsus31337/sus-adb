"""Immutable, GUI-neutral view descriptions returned by plugin factories."""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Mapping

@dataclass(frozen=True,slots=True)
class PluginView:
    name:str;body:str="";rows:tuple[tuple[str,str],...]=();warning:str=""

@dataclass(frozen=True,slots=True)
class PluginPanelSpec:
    title:str;views:tuple[PluginView,...];status:Mapping[str,str]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"status",dict(self.status))

def empty_views(names,message="No device, target, or assessment is selected."):
    return tuple(PluginView(name,message) for name in names)
