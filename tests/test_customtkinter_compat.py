import contextlib,io,tkinter as tk,unittest
from app.gui.customtkinter_compat import install_scroll_target_guard

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
