"""Narrow application-owned compatibility guards for CustomTkinter."""
from __future__ import annotations
import functools
import tkinter as tk
from dataclasses import dataclass

_SENTINEL="_susadb_scroll_target_guard_installed"
_VALIDATORS=("_check_if_valid_scroll","check_if_master_is_canvas")

@dataclass(frozen=True,slots=True)
class ScrollGuardResult:
    installed:bool;method_name:str=""

def install_scroll_target_guard(scrollable_class=None):
    """Guard CTk's global wheel validator; preserve all valid-widget behavior."""
    if scrollable_class is None:
        import customtkinter as ctk
        scrollable_class=ctk.CTkScrollableFrame
    if getattr(scrollable_class,_SENTINEL,False):
        return ScrollGuardResult(False,getattr(scrollable_class,_SENTINEL))
    method_name=next((name for name in _VALIDATORS if callable(getattr(scrollable_class,name,None))),"")
    if not method_name:return ScrollGuardResult(False)
    original=getattr(scrollable_class,method_name)
    @functools.wraps(original)
    def guarded(self,widget):
        if not isinstance(widget,tk.Misc):return False
        try:return bool(original(self,widget))
        except (AttributeError,tk.TclError):return False
    setattr(scrollable_class,method_name,guarded);setattr(scrollable_class,_SENTINEL,method_name)
    return ScrollGuardResult(True,method_name)
