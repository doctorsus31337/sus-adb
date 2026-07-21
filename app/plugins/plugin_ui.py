"""Immutable, GUI-neutral view descriptions returned by plugin factories."""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
import re
from typing import Mapping

class AddonUIMode(str,Enum):
    EMBEDDED="embedded";WINDOW="window";HYBRID="hybrid"

@dataclass(frozen=True,slots=True)
class PluginView:
    name:str;body:str="";rows:tuple[tuple[str,str],...]=();warning:str=""

@dataclass(frozen=True,slots=True)
class PluginPanelSpec:
    title:str;views:tuple[PluginView,...];status:Mapping[str,str]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"status",dict(self.status))

@dataclass(frozen=True,slots=True)
class AddonWindowSpec:
    contribution_id:str;title:str;panel:PluginPanelSpec;preferred_mode:AddonUIMode=AddonUIMode.WINDOW
    default_width:int=1080;default_height:int=720;minimum_width:int=820;minimum_height:int=560
    singleton:bool=True;embedded_summary:bool=False;icon:str="⚙";status:Mapping[str,str]=field(default_factory=dict)
    def __post_init__(self):
        object.__setattr__(self,"preferred_mode",AddonUIMode(self.preferred_mode));object.__setattr__(self,"status",dict(self.status))

@dataclass(frozen=True,slots=True)
class AddonCardSpec:
    plugin_id:str;name:str;version:str;description:str;capability_count:int;official:bool=True
    high_impact:bool=False;lifecycle_status:str="Available";diagnostic:str="";preferred_mode:AddonUIMode=AddonUIMode.WINDOW;privacy_note:str=""
    def __post_init__(self):object.__setattr__(self,"preferred_mode",AddonUIMode(self.preferred_mode))

def resolve_ui_mode(value,default=AddonUIMode.WINDOW):
    try:return AddonUIMode(value)
    except (TypeError,ValueError):return default

def clamp_addon_geometry(value,screen_w,screen_h,spec):
    match=re.fullmatch(r"(\d+)x(\d+)(?:\+(-?\d+)\+(-?\d+))?",str(value or ""))
    if match:w,h,x,y=(int(v or 0) for v in match.groups())
    else:w,h,x,y=spec.default_width,spec.default_height,(screen_w-spec.default_width)//2,(screen_h-spec.default_height)//2
    w=max(spec.minimum_width,min(w,screen_w));h=max(spec.minimum_height,min(h,screen_h));x=max(0,min(x,screen_w-w));y=max(0,min(y,screen_h-h))
    return f"{w}x{h}+{x}+{y}"

def empty_views(names,message="No device, target, or assessment is selected."):
    return tuple(PluginView(name,message) for name in names)
