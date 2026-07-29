import builtins,io,unittest
from contextlib import redirect_stderr,redirect_stdout
from unittest.mock import patch
import main
from app.core import branding_dependencies
class ApplicationStartupTests(unittest.TestCase):
 def setUp(self):branding_dependencies._reset_notice_for_tests()
 def test_version_and_self_test_do_not_import_gui(self):
  out=io.StringIO()
  with patch.dict("sys.modules",{"app.gui.main_window":None}),redirect_stdout(out):self.assertEqual(main.cli(["--version"]),0)
  self.assertIn("1.0.0-rc.4",out.getvalue())
 def test_cli_identity_is_preferred_while_legacy_entry_remains_documented(self):
  self.assertEqual(main.METADATA.preferred_executable,"sus-companion");self.assertEqual(main.METADATA.legacy_executable,"sus-adb")
 def test_diagnostics_prints_build_identity_before_tool_results(self):
  out=io.StringIO()
  with patch("main.EnvironmentDiagnostics.run",return_value=()),redirect_stdout(out):self.assertEqual(main.cli(["--diagnostics"]),0)
  text=out.getvalue();self.assertIn("BUILD\tProduct version\t",text);self.assertIn("BUILD\tCommit\t",text);self.assertIn("BUILD\tBranch/ref\t",text);self.assertIn("BUILD\tBuild timestamp\t",text);self.assertIn("BUILD\tBuild channel\t",text)
 def test_missing_pillow_gui_import_has_concise_dependency_guidance(self):
  actual=builtins.__import__;err=io.StringIO()
  def missing(name,*args,**kwargs):
   if name=="app.gui.main_window":raise ModuleNotFoundError("No module named 'PIL'",name="PIL")
   return actual(name,*args,**kwargs)
  with patch("builtins.__import__",side_effect=missing),patch("subprocess.run") as run,redirect_stderr(err):
   self.assertEqual(main.cli([]),1)
  self.assertIn("python -m pip install -r requirements.txt -c constraints.txt",err.getvalue());self.assertNotIn("Traceback",err.getvalue());run.assert_not_called()
 def test_unrelated_gui_import_error_is_not_hidden(self):
  actual=builtins.__import__
  def missing(name,*args,**kwargs):
   if name=="app.gui.main_window":raise ModuleNotFoundError("No module named 'other'",name="other")
   return actual(name,*args,**kwargs)
  with patch("builtins.__import__",side_effect=missing),self.assertRaises(ModuleNotFoundError):main.cli([])
if __name__=="__main__":unittest.main()
