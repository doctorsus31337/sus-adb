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
if __name__=="__main__":unittest.main()
