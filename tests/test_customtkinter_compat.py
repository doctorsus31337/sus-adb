import contextlib,io,tkinter as tk,unittest
from types import SimpleNamespace
from app.gui.customtkinter_compat import PendingCallbackOwner,ScopedScrollRouter,clamp_scroll_offset,install_scroll_target_guard,keyboard_focus_target,safe_focus,wheel_scroll_units

def widget(master=None):
    value=object.__new__(tk.Misc);value.master=master;return value

class T(unittest.TestCase):
 def scroll_class(self,name="_check_if_valid_scroll"):
  def validate(self,target):
   if target is self._parent_canvas:return True
   if target.master is not None:return validate(self,target.master)
   return False
  return type("SyntheticScrollable",(),{name:validate})
 def test_string_and_tcl_path_targets_are_safely_ignored(self):
  cls=self.scroll_class();result=install_scroll_target_guard(cls);self.assertTrue(result.installed);frame=cls();frame._parent_canvas=widget()
  with contextlib.redirect_stderr(io.StringIO()) as errors:
   for target in ("str",".native.file.dialog")*20:self.assertFalse(frame._check_if_valid_scroll(target))
  self.assertEqual(errors.getvalue(),"")
 def test_valid_widget_and_child_keep_normal_validation(self):
  cls=self.scroll_class();install_scroll_target_guard(cls);frame=cls();canvas=widget();child=widget(canvas);frame._parent_canvas=canvas;self.assertTrue(frame._check_if_valid_scroll(canvas));self.assertTrue(frame._check_if_valid_scroll(child));self.assertFalse(frame._check_if_valid_scroll(widget()))
 def test_stale_widget_does_not_raise(self):
  class Stale(tk.Misc):
   @property
   def master(self):raise tk.TclError("destroyed")
  cls=self.scroll_class();install_scroll_target_guard(cls);frame=cls();frame._parent_canvas=widget();self.assertFalse(frame._check_if_valid_scroll(object.__new__(Stale)))
 def test_install_is_idempotent_for_multiple_instances(self):
  cls=self.scroll_class();first=install_scroll_target_guard(cls);method=cls._check_if_valid_scroll;second=install_scroll_target_guard(cls);self.assertTrue(first.installed);self.assertFalse(second.installed);self.assertIs(method,cls._check_if_valid_scroll)
  for _ in range(3):frame=cls();frame._parent_canvas=widget();self.assertFalse(frame._check_if_valid_scroll(".dialog"))
 def test_customtkinter_52_validator_name_is_supported(self):
  cls=self.scroll_class("check_if_master_is_canvas");result=install_scroll_target_guard(cls);frame=cls();frame._parent_canvas=widget();self.assertEqual(result.method_name,"check_if_master_is_canvas");self.assertFalse(frame.check_if_master_is_canvas(".dialog"));self.assertTrue(frame.check_if_master_is_canvas(frame._parent_canvas))
 def test_windows_style_delayed_callback_ignores_destroyed_owner(self):
  class FakeWidget:
   def __init__(self):self.exists=True;self.callbacks={};self.cancelled=[];self.counter=0
   def winfo_exists(self):return self.exists
   def after(self,_delay,callback):self.counter+=1;key=f"after#{self.counter}";self.callbacks[key]=callback;return key
   def after_cancel(self,key):self.cancelled.append(key);self.callbacks.pop(key,None)
  owner_widget=FakeWidget();owner=PendingCallbackOwner(owner_widget);called=[];owner.schedule(0,lambda:called.append(True));owner_widget.exists=False
  for callback in tuple(owner_widget.callbacks.values()):callback()
  self.assertEqual(called,[])
 def test_pending_callbacks_are_cancelled_on_close(self):
  class FakeWidget:
   def __init__(self):self.callbacks={};self.cancelled=[]
   def winfo_exists(self):return True
   def after(self,_delay,callback):key=f"after#{len(self.callbacks)+1}";self.callbacks[key]=callback;return key
   def after_cancel(self,key):self.cancelled.append(key)
  target=FakeWidget();owner=PendingCallbackOwner(target);owner.schedule(0,lambda:None);owner.cancel_all();self.assertEqual(target.cancelled,["after#1"])
 def test_safe_focus_only_suppresses_destroyed_widget_tclerror(self):
  class Stale:
   def winfo_exists(self):return True
   def focus_set(self):raise tk.TclError("bad window path name")
  self.assertFalse(safe_focus(Stale()))
 def test_keyboard_focus_target_uses_guarded_composed_surface_or_fallback(self):
  outer=widget();canvas=widget(outer);outer._canvas=canvas
  outer.winfo_exists=lambda:1;canvas.winfo_exists=lambda:1
  self.assertIs(keyboard_focus_target(outer),canvas)
  plain=widget();plain.winfo_exists=lambda:1
  self.assertIs(keyboard_focus_target(plain),plain)
  outer._canvas=object()
  self.assertIs(keyboard_focus_target(outer),outer)
 def test_windows_and_touchpad_wheel_deltas_are_normalized(self):
  self.assertEqual(wheel_scroll_units(SimpleNamespace(delta=120)),-3)
  self.assertEqual(wheel_scroll_units(SimpleNamespace(delta=-240)),6)
  self.assertEqual(wheel_scroll_units(SimpleNamespace(delta=1)),-3)
  self.assertEqual(wheel_scroll_units(SimpleNamespace(delta=-1)),3)
  self.assertEqual(wheel_scroll_units(SimpleNamespace(delta=0)),0)
 def test_linux_x11_wheel_buttons_are_normalized(self):
  self.assertEqual(wheel_scroll_units(SimpleNamespace(num=4,delta=0)),-3)
  self.assertEqual(wheel_scroll_units(SimpleNamespace(num=5,delta=0)),3)
 def test_scroll_offset_clamps_after_filter_and_resize(self):
  self.assertEqual(clamp_scroll_offset(900,1800,500),900)
  self.assertEqual(clamp_scroll_offset(1600,1800,500),1300)
  self.assertEqual(clamp_scroll_offset(900,400,500),0)
  self.assertEqual(clamp_scroll_offset(-10,1800,500),0)
 def test_nested_boundary_direction_is_exact(self):
  class View:
   def __init__(self,first,last):self.first=first;self.last=last
   def yview(self):return self.first,self.last
  self.assertTrue(ScopedScrollRouter._can_scroll(View(.2,.8),-3))
  self.assertTrue(ScopedScrollRouter._can_scroll(View(.2,.8),3))
  self.assertFalse(ScopedScrollRouter._can_scroll(View(0,.8),-3))
  self.assertFalse(ScopedScrollRouter._can_scroll(View(.2,1),3))
 def test_editing_and_choice_controls_are_excluded(self):
  Entry=type("CTkEntry",(tk.Misc,),{})
  Combo=type("CTkComboBox",(tk.Misc,),{})
  entry=object.__new__(Entry);entry.master=None
  combo=object.__new__(Combo);combo.master=None
  child=widget(entry)
  self.assertTrue(ScopedScrollRouter._editing_control(child))
  self.assertTrue(ScopedScrollRouter._choice_control(combo))
  self.assertFalse(ScopedScrollRouter._choice_control(widget()))
