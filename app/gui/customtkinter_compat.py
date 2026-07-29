"""Narrow application-owned compatibility guards for CustomTkinter."""
from __future__ import annotations
import functools
import tkinter as tk
import weakref
from dataclasses import dataclass

try:
    import customtkinter as ctk
except ModuleNotFoundError:
    ctk=None

_SENTINEL="_susadb_scroll_target_guard_installed"
_VALIDATORS=("_check_if_valid_scroll","check_if_master_is_canvas")
_WHEEL_EVENTS=("<MouseWheel>","<Button-4>","<Button-5>")
_SCROLL_KEYS=("<Prior>","<Next>","<Home>","<End>","<Up>","<Down>")

@dataclass(frozen=True,slots=True)
class ScrollGuardResult:
    installed:bool;method_name:str=""

def wheel_scroll_units(event,lines=3):
    """Normalize Tk wheel events without depending on the host platform."""
    button=getattr(event,"num",None)
    if button==4:return -max(1,int(lines))
    if button==5:return max(1,int(lines))
    try:delta=int(getattr(event,"delta",0))
    except (TypeError,ValueError):return 0
    if not delta:return 0
    steps=max(1,abs(delta)//120)
    return (-steps if delta>0 else steps)*max(1,int(lines))

def clamp_scroll_offset(offset,content_height,viewport_height):
    """Clamp an absolute canvas offset after content or viewport changes."""
    maximum=max(0.0,float(content_height)-float(viewport_height))
    return min(max(0.0,float(offset)),maximum)

def widget_exists(widget):
    """Return False for destroyed or partially torn-down Tk widgets."""
    if widget is None:return False
    try:return bool(widget.winfo_exists())
    except (AttributeError,tk.TclError):return False

def widget_within(widget,container):
    """Return true only when a live Tk widget belongs to one owned container."""
    if not isinstance(widget,tk.Misc) or not widget_exists(container):return False
    seen=set()
    try:
        while widget is not None and id(widget) not in seen:
            if widget is container:return True
            seen.add(id(widget));widget=getattr(widget,"master",None)
    except (AttributeError,tk.TclError):return False
    return False

def safe_focus(widget):
    """Focus a live widget without masking exceptions from unrelated work."""
    if not widget_exists(widget):return False
    try:widget.focus_set();return True
    except tk.TclError:return False

def keyboard_focus_target(widget):
    """Resolve the Tk widget that owns focus for a composed CTk control."""
    if not widget_exists(widget):return None
    candidate=getattr(widget,"_canvas",None)
    if isinstance(candidate,tk.Misc) and widget_exists(candidate):return candidate
    return widget if isinstance(widget,tk.Misc) else None

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
    def _schedule(self,scheduler,callback,*args):
        widget=self._widget()
        if self._closed or not widget_exists(widget):return None
        callback_id=None
        def guarded():
            self._pending.discard(callback_id)
            owner=self._widget()
            if not self._closed and widget_exists(owner):callback(*args)
        callback_id=scheduler(guarded);self._pending.add(callback_id);return callback_id
    def schedule(self,delay_ms,callback,*args):
        widget=self._widget()
        if not widget_exists(widget):return None
        return self._schedule(lambda guarded:widget.after(delay_ms,guarded),callback,*args)
    def schedule_idle(self,callback,*args):
        widget=self._widget()
        if not widget_exists(widget):return None
        return self._schedule(widget.after_idle,callback,*args)
    def cancel_all(self):
        self._closed=True;widget=self._widget()
        if widget_exists(widget):
            for callback_id in tuple(self._pending):
                try:widget.after_cancel(callback_id)
                except tk.TclError:pass
        self._pending.clear()

class ScopedEventBindings:
    """Track additive widget bindings and remove exactly those bindings."""
    def __init__(self):self._bindings=[];self._closed=False
    @property
    def count(self):return len(self._bindings)
    def bind(self,owner,sequence,callback):
        if self._closed or not widget_exists(owner):return None
        binding_id=owner.bind(sequence,callback,add="+")
        if binding_id:self._bindings.append((weakref.ref(owner),sequence,binding_id))
        return binding_id
    def close(self):
        self._closed=True
        for owner_ref,sequence,binding_id in tuple(self._bindings):
            owner=owner_ref()
            if widget_exists(owner):
                try:owner.unbind(sequence,binding_id)
                except tk.TclError:pass
        self._bindings.clear()

class ScopedScrollRouter:
    """Route wheel and keyboard input to one live, visible owned viewport."""
    def __init__(
        self,viewport,scroll_target,*,owner=None,orientation="vertical",
        keyboard=True,native_dialog_guard=None,visible=None,scroll_units=36,
    ):
        self._viewport=weakref.ref(viewport)
        self._target=weakref.ref(scroll_target)
        resolved_owner=owner or viewport.winfo_toplevel()
        self._owner=weakref.ref(resolved_owner)
        self.orientation=orientation
        self.keyboard=bool(keyboard)
        self.native_dialog_guard=native_dialog_guard
        self.visible=visible
        self.scroll_units=max(1,int(scroll_units))
        self.bindings=ScopedEventBindings()
        self.nested_bindings=ScopedEventBindings()
        self.callbacks=PendingCallbackOwner(viewport)
        self._nested=[]
        self._closed=False
        try:scroll_target.configure(takefocus=True)
        except tk.TclError:pass
        for sequence in _WHEEL_EVENTS:
            self.bindings.bind(resolved_owner,sequence,self._wheel)
        if self.keyboard:
            for sequence in _SCROLL_KEYS:
                self.bindings.bind(resolved_owner,sequence,self._key)
        self.bindings.bind(resolved_owner,"<FocusIn>",self._focus_in)
        self.bindings.bind(scroll_target,"<Button-1>",self._focus_viewport)
        self.bindings.bind(viewport,"<Button-1>",self._focus_viewport)

    @property
    def count(self):
        return self.bindings.count+self.nested_bindings.count

    def _widgets(self):
        return self._viewport(),self._target(),self._owner()

    def _root(self):
        viewport=self._viewport()
        return getattr(viewport,"_parent_frame",viewport)

    def _inside(self,widget):
        viewport,target,_owner=self._widgets()
        root=self._root()
        if widget in {
            viewport,target,root,
            getattr(viewport,"_scrollbar",None),
        }:
            return True
        return widget_within(widget,root)

    @staticmethod
    def _control_ancestor(widget,names):
        seen=set()
        try:
            while isinstance(widget,tk.Misc) and id(widget) not in seen:
                if widget.__class__.__name__ in names:return widget
                seen.add(id(widget));widget=getattr(widget,"master",None)
        except (AttributeError,tk.TclError):return None
        return None

    @classmethod
    def _editing_control(cls,widget):
        return cls._control_ancestor(widget,{
            "Entry","Spinbox","Text","CTkEntry","CTkTextbox","CTkComboBox",
        }) is not None

    @classmethod
    def _choice_control(cls,widget):
        return cls._control_ancestor(widget,{
            "Listbox","TCombobox","CTkComboBox","DropdownMenu",
        }) is not None

    def _available(self):
        viewport,target,owner=self._widgets()
        if self._closed or not all(widget_exists(value) for value in (viewport,target,owner)):
            return False
        if self.native_dialog_guard is not None:
            try:
                if self.native_dialog_guard():return False
            except tk.TclError:return False
        if self.visible is not None:
            try:
                if not self.visible():return False
            except tk.TclError:return False
        root=self._root()
        try:
            ancestor=root
            while isinstance(ancestor,tk.Misc):
                parent=getattr(ancestor,"master",None)
                if parent is None:break
                if parent.__class__.__name__=="CTkTabview":
                    selected=getattr(parent,"_tab_dict",{}).get(
                        getattr(parent,"_current_name","")
                    )
                    if selected is None or not (
                        root is selected or widget_within(root,selected)
                    ):
                        return False
                ancestor=parent
        except (AttributeError,tk.TclError):
            return False
        try:
            return bool(root.winfo_ismapped() and target.winfo_ismapped())
        except (AttributeError,tk.TclError):
            return False

    @staticmethod
    def _can_scroll(widget,units):
        try:
            first,last=widget.yview()
            return units<0 and first>0.0001 or units>0 and last<0.9999
        except (AttributeError,tk.TclError):
            return False

    def register_nested(self,widget):
        """Give a text/list child first chance, then bubble at its boundary."""
        inner=getattr(widget,"_textbox",widget)
        if not isinstance(inner,tk.Misc) or not widget_exists(inner):return False
        if any(ref() is inner for ref in self._nested):return True
        self._nested.append(weakref.ref(inner))
        for sequence in _WHEEL_EVENTS:
            self.nested_bindings.bind(inner,sequence,self._nested_wheel)
        return True

    def clear_nested(self):
        self.nested_bindings.close()
        self.nested_bindings=ScopedEventBindings()
        self._nested.clear()

    def _nested_for(self,origin):
        live=[]
        found=None
        for reference in self._nested:
            widget=reference()
            if widget_exists(widget):
                live.append(reference)
                if widget_within(origin,widget):found=widget
        self._nested=live
        return found

    def _nested_wheel(self,event):
        origin=getattr(event,"widget",None)
        nested=self._nested_for(origin)
        units=wheel_scroll_units(event,lines=3)
        if nested is None or not units:return None
        if not self._can_scroll(nested,units):return None
        try:nested.yview_scroll(units,"units")
        except tk.TclError:return None
        return "break"

    def _wheel(self,event):
        origin=getattr(event,"widget",None)
        if not self._available() or not self._inside(origin):return None
        if self._choice_control(origin):return None
        units=wheel_scroll_units(event,lines=self.scroll_units)
        if not units:return None
        nested=self._nested_for(origin)
        if nested is not None and self._can_scroll(nested,units):return "break"
        _viewport,target,_owner=self._widgets()
        try:
            if self.orientation=="horizontal":
                if not (int(getattr(event,"state",0))&0x0001):return None
                target.xview_scroll(units,"units")
            else:
                target.yview_scroll(units,"units")
        except (AttributeError,tk.TclError):return None
        return "break"

    def _key(self,event):
        origin=getattr(event,"widget",None)
        keysym=getattr(event,"keysym","")
        if (
            not self._available() or not self._inside(origin)
            or self.orientation!="vertical"
        ):
            return None
        if self._editing_control(origin) or self._choice_control(origin):return None
        _viewport,target,_owner=self._widgets()
        try:
            if keysym=="Prior":target.yview_scroll(-1,"pages")
            elif keysym=="Next":target.yview_scroll(1,"pages")
            elif keysym=="Home":target.yview_moveto(0)
            elif keysym=="End":target.yview_moveto(1)
            elif keysym=="Up":target.yview_scroll(-self.scroll_units,"units")
            elif keysym=="Down":target.yview_scroll(self.scroll_units,"units")
            else:return None
        except (AttributeError,tk.TclError):return None
        return "break"

    def _focus_viewport(self,event):
        origin=getattr(event,"widget",None)
        _viewport,target,_owner=self._widgets()
        if origin is target and self._available():safe_focus(target)
        return None

    def _focus_in(self,event):
        origin=getattr(event,"widget",None)
        if self._available() and self._inside(origin):
            self.callbacks.schedule_idle(self.ensure_visible,origin)
        return None

    def ensure_visible(self,widget):
        if not self._available() or not self._inside(widget):return
        viewport,target,_owner=self._widgets()
        if widget in {viewport,target,self._root()}:return
        try:
            top=widget.winfo_rooty()-viewport.winfo_rooty()+target.canvasy(0)
            bottom=top+max(1,widget.winfo_height())
            view_top=target.canvasy(0)
            view_height=max(1,target.winfo_height())
            region=tuple(float(value) for value in str(target.cget("scrollregion")).split())
            extent=region[3]-region[1] if len(region)==4 else 0.0
            destination=view_top
            if top<view_top:destination=top
            elif bottom>view_top+view_height:destination=bottom-view_height
            destination=clamp_scroll_offset(destination,extent,view_height)
            target.yview_moveto(destination/extent if extent else 0)
        except (AttributeError,TypeError,ValueError,tk.TclError):
            return

    def close(self):
        if self._closed:return
        self._closed=True
        self.callbacks.cancel_all()
        self.nested_bindings.close()
        self.bindings.close()
        self._nested.clear()

class ScopedScrollableFrame(ctk.CTkScrollableFrame if ctk is not None else object):
    """CTk scroll frame with instance-owned input and deterministic cleanup."""
    _GLOBAL_INPUT=(
        "<MouseWheel>","<KeyPress-Shift_L>","<KeyPress-Shift_R>",
        "<KeyRelease-Shift_L>","<KeyRelease-Shift_R>",
    )
    def __init__(self,*args,scroll_keyboard=True,scroll_units=36,**kwargs):
        self._susadb_building=True
        super().__init__(*args,**kwargs)
        self._susadb_building=False
        self._scroll_router=ScopedScrollRouter(
            self,self._parent_canvas,orientation=self._orientation,
            keyboard=scroll_keyboard,scroll_units=scroll_units,
        )
    def bind_all(self,sequence=None,func=None,add=None):
        if getattr(self,"_susadb_building",False) and sequence in self._GLOBAL_INPUT:
            return None
        return super().bind_all(sequence,func,add)
    def register_nested_scroll(self,widget):
        return self._scroll_router.register_nested(widget)
    def clear_nested_scrolls(self):
        self._scroll_router.clear_nested()
    def destroy(self):
        router=getattr(self,"_scroll_router",None)
        if router is not None:router.close()
        super().destroy()

class DeterministicTabview(ctk.CTkTabview if ctk is not None else object):
    """Select tabs synchronously without CTk's stale delayed forget callback."""
    def _select_synchronously(self,name,*,invoke_command=False):
        if name not in self._tab_dict:
            raise ValueError(f"CTkTabview has no tab named '{name}'")
        previous=self._tab_dict.get(self._current_name)
        if previous is not None and self._current_name!=name:
            previous.grid_forget()
        self._current_name=name
        self._segmented_button.set(name)
        self._set_grid_current_tab()
        if invoke_command and self._command is not None:
            self._command()
    def set(self,name):
        self._select_synchronously(name)
    def _segmented_button_callback(self,selected_name):
        self._select_synchronously(selected_name,invoke_command=True)

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
