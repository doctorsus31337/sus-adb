import json,tempfile,unittest
from pathlib import Path
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
class T(unittest.TestCase):
 def test_install_trust_enable_load_separation_inventory_changed_quarantine(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/"src";src.mkdir();(src/"manifest.json").write_text(json.dumps({"plugin_id":"demo","name":"D","version":"1.0.0","entry_point":"plugin.py:Plugin","requested_capabilities":[]}));(src/"plugin.py").write_text("class Plugin:\n def activate(self,api): return ()\n def deactivate(self): pass\n")
   store=PluginStore(Path(d)/"store");trust=PluginTrustStore(store.root/"state/trust.json");m=PluginManager(store,trust,ContributionRegistry());self.assertTrue(m.install(src).ok);self.assertFalse(m.load("demo").ok);self.assertTrue(m.approve("demo").ok);self.assertTrue(m.enable("demo").ok);self.assertTrue(m.load("demo").ok);self.assertTrue(m.unload("demo").ok);inventory=m.export_inventory(store.root/"state/inventory.json");self.assertTrue(Path(inventory).exists());path=m.records["demo"][0];(path/"plugin.py").write_text("changed");self.assertFalse(m.verify("demo").ok);self.assertFalse(trust.verify("demo","anything"))
