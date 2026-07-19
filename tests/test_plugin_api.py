import tempfile,unittest
from app.plugins.plugin_api import PluginAPI
class T(unittest.TestCase):
 def test_gated_facades_and_sanitized_state(self):
  with tempfile.TemporaryDirectory() as d:
   a=PluginAPI("p",state_root=d);self.assertFalse(a.run_adb_readonly(("getprop",)).ok);b=PluginAPI("p",("run-adb-readonly","write-plugin-state","read-local-plugin-files"),state_root=d,adb_readonly=lambda x:x);self.assertTrue(b.run_adb_readonly(("getprop",)).ok);self.assertFalse(b.run_adb_readonly(("rm",)).ok);self.assertTrue(b.write_state({"x":1}).ok);self.assertEqual(b.read_state().value,{"x":1})
