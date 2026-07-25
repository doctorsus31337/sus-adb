import json,tempfile,unittest
from pathlib import Path
from app.plugins.plugin_store import PluginStore
class T(unittest.TestCase):
 def test_install_disabled_no_execution_and_uninstall_confirmation(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/"src";src.mkdir();(src/"manifest.json").write_text(json.dumps({"plugin_id":"demo","name":"D","version":"1.0.0"}));(src/"plugin.py").write_text("raise Exception('never')")
   store=PluginStore(Path(d)/"store");r=store.install(src);self.assertTrue(r.ok);self.assertFalse(store.state("demo")["enabled"]);self.assertFalse(store.uninstall("demo","1.0.0").ok);self.assertTrue(store.uninstall("demo","1.0.0",True).ok);self.assertTrue((store.root/"state"/"demo.json").exists())
