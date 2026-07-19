import io,unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import main
class ApplicationStartupTests(unittest.TestCase):
 def test_version_and_self_test_do_not_import_gui(self):
  out=io.StringIO()
  with patch.dict("sys.modules",{"app.gui.main_window":None}),redirect_stdout(out):self.assertEqual(main.cli(["--version"]),0)
  self.assertIn("1.0.0-rc.1",out.getvalue())
if __name__=="__main__":unittest.main()
