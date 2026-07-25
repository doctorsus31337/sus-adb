"""Narrow application-owned compatibility guards for CustomTkinter."""
from __future__ import annotations
import functools
import tkinter as tk
import weakref
from dataclasses import dataclass

_SENTINEL="_susadb_scroll_target_guard_installed"
_VALIDATORS=("_check_if_valid_scroll","check_if_master_is_canvas")

@dataclass(frozen=True,slots=True)
class ScrollGuardResult:
    installed:bool;method_name:str=""

def widget_exists(widget):
    """Return False for destroyed or partially torn-down Tk widgets."""
    if widget is None:return False
    try:return bool(widget.winfo_exists())
    except (AttributeError,tk.TclError):return False

def safe_focus(widget):
    """Focus a live widget without masking exceptions from unrelated work."""
    if not widget_exists(widget):return False
    try:widget.focus_set();return True
    except tk.TclError:return False

def focused_within(widget):
    if not widget_exists(widget):return False
    try:
        focused=widget.focus_get()
        while focused is not None:
            if focused is widget:return True
            focused=getattr(focused,"master",None)
    except (AttributeError,tk.TclError):return False
    return False

class PendingCallbackOwner:
    """Tracks only callbacks scheduled by one host and cancels them on close."""
    def __init__(self,widget):self._widget=weakref.ref(widget);self._pending=set();self._closed=False
    def schedule(self,delay_ms,callback,*args):
        widget=self._widget()
        if self._closed or not widget_exists(widget):return None
        callback_id=None
        def guarded():
            self._pending.discard(callback_id)
            owner=self._widget()
            if not self._closed and widget_exists(owner):callback(*args)
        callback_id=widget.after(delay_ms,guarded);self._pending.add(callback_id);return callback_id
    def cancel_all(self):
        self._closed=True;widget=self._widget()
        if widget_exists(widget):
            for callback_id in tuple(self._pending):
                try:widget.after_cancel(callback_id)
                except tk.TclError:pass
        self._pending.clear()

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
