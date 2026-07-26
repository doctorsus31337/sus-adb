"""Immutable, GUI-neutral Plugin API 1.1 interactive contracts."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any,Callable,Mapping
from app.plugins.plugin_api import PluginContext

MAX_TEXT_LENGTH=16_384
class PluginFieldType(str,Enum):
    TEXT="text";PASSWORD="password";MULTILINE="multiline";CHECKBOX="checkbox";CHOICE="choice";INTEGER="integer";READ_ONLY="read_only"
class PluginActionClassification(str,Enum):
    INFORMATIONAL="informational";NAVIGATION="navigation";READ_ONLY="read_only";STATE_CHANGING="state_changing"
class PluginRefreshBehavior(str,Enum):NONE="none";PANEL="panel"
class PluginContextBinding(str,Enum):NONE="none";DEVICE="device";TARGET="target";DEVICE_AND_TARGET="device_and_target"
PLUGIN_NAVIGATION_DESTINATIONS=("workspace-home","console","instrumentation","script-studio","pentest","addons-center","sessions-center","workflow-recipes","environment-diagnostics","contextual-help","plugin-workbench")

def _id(value,label):
    value=str(value)
    if not value or len(value)>96 or not all(c.isalnum() or c in "._-" for c in value):raise ValueError(f"{label} must be a stable identifier.")
    return value
def _text(value,limit=2_000):return str(value or "")[:limit]

@dataclass(frozen=True,slots=True)
class PluginOptionSpec:
    option_id:str;label:str
    def __post_init__(self):object.__setattr__(self,"option_id",_id(self.option_id,"Option ID"));object.__setattr__(self,"label",_text(self.label,160))
@dataclass(frozen=True,slots=True)
class PluginFieldSpec:
    field_id:str;label:str;field_type:PluginFieldType=PluginFieldType.TEXT;description:str="";required:bool=False;default:Any=None;placeholder:str="";options:tuple[PluginOptionSpec,...]=();minimum:int|None=None;maximum:int|None=None;max_length:int=1_024;sensitive:bool=False;validation_hint:str=""
    def __post_init__(self):
        object.__setattr__(self,"field_id",_id(self.field_id,"Field ID"));object.__setattr__(self,"field_type",PluginFieldType(self.field_type));object.__setattr__(self,"options",tuple(self.options))
        if not 1<=self.max_length<=MAX_TEXT_LENGTH:raise ValueError("Field max_length is outside the host bound.")
        if self.minimum is not None and self.maximum is not None and self.minimum>self.maximum:raise ValueError("Field minimum cannot exceed maximum.")
        ids=tuple(v.option_id for v in self.options)
        if len(ids)!=len(set(ids)):raise ValueError("Choice option IDs must be unique.")
        if self.field_type is PluginFieldType.CHOICE and not self.options:raise ValueError("Choice fields require options.")
        if self.default is not None:validate_field_value(self,self.default)
@dataclass(frozen=True,slots=True)
class PluginFormSpec:
    form_id:str;fields:tuple[PluginFieldSpec,...];title:str="";description:str=""
    def __post_init__(self):
        object.__setattr__(self,"form_id",_id(self.form_id,"Form ID"));object.__setattr__(self,"fields",tuple(self.fields));ids=tuple(v.field_id for v in self.fields)
        if len(ids)!=len(set(ids)):raise ValueError("Field IDs must be unique inside a form.")
@dataclass(frozen=True,slots=True)
class PluginConfirmationSpec:
    summary:str;technical_preview:str="";typed_phrase:str=""
    def __post_init__(self):object.__setattr__(self,"summary",_text(self.summary));object.__setattr__(self,"technical_preview",_text(self.technical_preview));object.__setattr__(self,"typed_phrase",_text(self.typed_phrase,80))
@dataclass(frozen=True,slots=True)
class PluginNavigationSpec:
    destination:str
    def __post_init__(self):
        if self.destination not in PLUGIN_NAVIGATION_DESTINATIONS:raise ValueError("Unknown host navigation destination.")
@dataclass(frozen=True,slots=True)
class PluginProgressUpdate:
    text:str="";value:float|None=None
    def __post_init__(self):
        object.__setattr__(self,"text",_text(self.text,240))
        if self.value is not None and not 0<=float(self.value)<=1:raise ValueError("Progress value must be between zero and one.")
@dataclass(frozen=True,slots=True)
class PluginActionRequest:
    action_id:str;values:Mapping[str,Any];context:PluginContext;selected_serial:str="";selected_target:str="";cancelled:Callable[[],bool]=lambda:False;progress:Callable[[PluginProgressUpdate],None]=lambda _update:None
    def __post_init__(self):object.__setattr__(self,"values",MappingProxyType(dict(self.values)))
@dataclass(frozen=True,slots=True)
class PluginActionResult:
    ok:bool;message:str="";rows:tuple[tuple[str,str],...]=();panel:Any=None;navigation:PluginNavigationSpec|None=None;retry_guidance:str="";error_code:str=""
    def __post_init__(self):object.__setattr__(self,"message",_text(self.message));object.__setattr__(self,"rows",tuple((_text(k,160),_text(v,500)) for k,v in self.rows));object.__setattr__(self,"retry_guidance",_text(self.retry_guidance,500));object.__setattr__(self,"error_code",_text(self.error_code,80))
@dataclass(frozen=True,slots=True)
class PluginActionSpec:
    action_id:str;label:str;callback:Callable[[PluginActionRequest],PluginActionResult];description:str="";classification:PluginActionClassification=PluginActionClassification.INFORMATIONAL;required_capabilities:tuple[str,...]=();form:PluginFormSpec|None=None;confirmation:PluginConfirmationSpec|None=None;enabled:bool=True;unavailable_reason:str="";refresh:PluginRefreshBehavior=PluginRefreshBehavior.NONE;context_binding:PluginContextBinding=PluginContextBinding.NONE;supports_cancellation:bool=False;primary:bool=False
    def __post_init__(self):
        object.__setattr__(self,"action_id",_id(self.action_id,"Action ID"));object.__setattr__(self,"classification",PluginActionClassification(self.classification));object.__setattr__(self,"required_capabilities",tuple(sorted(set(self.required_capabilities))));object.__setattr__(self,"refresh",PluginRefreshBehavior(self.refresh));object.__setattr__(self,"context_binding",PluginContextBinding(self.context_binding))
        if not callable(self.callback):raise ValueError("Action callback is required.")
        if self.classification is PluginActionClassification.STATE_CHANGING and self.confirmation is None:raise ValueError("State-changing actions require confirmation.")

def validate_actions(actions):
    values=tuple(actions);ids=tuple(v.action_id for v in values)
    if len(ids)!=len(set(ids)):raise ValueError("Action IDs must be unique inside a panel.")
    return values
def validate_field_value(spec,value):
    if spec.field_type is PluginFieldType.CHECKBOX:
        if not isinstance(value,bool):raise ValueError(f"{spec.label} must be checked or unchecked.")
        return value
    if spec.field_type is PluginFieldType.INTEGER:
        if isinstance(value,bool):raise ValueError(f"{spec.label} must be an integer.")
        try:value=int(value)
        except (TypeError,ValueError) as exc:raise ValueError(f"{spec.label} must be an integer.") from exc
        if spec.minimum is not None and value<spec.minimum:raise ValueError(f"{spec.label} must be at least {spec.minimum}.")
        if spec.maximum is not None and value>spec.maximum:raise ValueError(f"{spec.label} must be at most {spec.maximum}.")
        return value
    value=str(value or "")
    if spec.required and not value.strip():raise ValueError(f"{spec.label} is required.")
    if len(value)>spec.max_length:raise ValueError(f"{spec.label} exceeds {spec.max_length} characters.")
    if spec.field_type is PluginFieldType.CHOICE and value not in {v.option_id for v in spec.options}:raise ValueError(f"{spec.label} must use an available choice.")
    return value
def validate_form(form,values):
    if form is None:return MappingProxyType({})
    return MappingProxyType({spec.field_id:validate_field_value(spec,values.get(spec.field_id,spec.default)) for spec in form.fields})
