import io,unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import main
class ApplicationStartupTests(unittest.TestCase):
 def test_version_and_self_test_do_not_import_gui(self):
  out=io.StringIO()
  with patch.dict("sys.modules",{"app.gui.main_window":None}),redirect_stdout(out):self.assertEqual(main.cli(["--version"]),0)
  self.assertIn("1.0.0-rc.1",out.getvalue())
 def test_cli_identity_is_preferred_while_legacy_entry_remains_documented(self):
  self.assertEqual(main.METADATA.preferred_executable,"sus-companion");self.assertEqual(main.METADATA.legacy_executable,"sus-adb")
 def test_diagnostics_prints_build_identity_before_tool_results(self):
  out=io.StringIO()
  with patch("main.EnvironmentDiagnostics.run",return_value=()),redirect_stdout(out):self.assertEqual(main.cli(["--diagnostics"]),0)
  text=out.getvalue();self.assertIn("BUILD\tProduct version\t",text);self.assertIn("BUILD\tCommit\t",text);self.assertIn("BUILD\tBranch/ref\t",text);self.assertIn("BUILD\tBuild timestamp\t",text);self.assertIn("BUILD\tBuild channel\t",text)
if __name__=="__main__":unittest.main()
