import json,tempfile,unittest
from pathlib import Path
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
from official_plugin_helpers import load
M=load("official_skeleton","skeleton_module");ROOT=Path(__file__).parents[1];SOURCE=ROOT/"plugins/official/skeleton_module"
class T(unittest.TestCase):
 def test_zero_capability_disabled_documented_noop(self):
  manifest=json.loads((SOURCE/"manifest.json").read_text());self.assertFalse(manifest["enabled"]);self.assertEqual(manifest["requested_capabilities"],[]);self.assertEqual(len(manifest["contributed_components"]),1);self.assertTrue(all((SOURCE/name).is_file() for name in ("README.md","TUTORIAL.md","ARCHITECTURE.md","EXERCISES.md","TROUBLESHOOTING.md","CHECKLIST.md","tests/test_lifecycle.py")));plugin=M.Plugin();self.assertTrue(plugin.validate().ok);self.assertEqual(len(plugin.activate(object())),1);plugin.deactivate();self.assertIsNone(plugin.api)
 def test_full_lifecycle_and_copy_new_id_without_core_edit(self):
  with tempfile.TemporaryDirectory() as d:
   store=PluginStore(Path(d)/"store");manager=PluginManager(store,PluginTrustStore(store.root/"state/trust.json"),ContributionRegistry());self.assertTrue(manager.install(SOURCE).ok);pid="susadb.skeleton-module";self.assertTrue(manager.trust_zero_capability(pid,True).ok);self.assertTrue(manager.enable(pid).ok);self.assertTrue(manager.load(pid).ok);self.assertEqual(len(manager.registry.list()),1);self.assertTrue(manager.unload(pid).ok);self.assertTrue(manager.uninstall(pid,True).ok)
   copied=Path(d)/"copy";__import__('shutil').copytree(SOURCE,copied);data=json.loads((copied/"manifest.json").read_text());data["plugin_id"]="learner.first-plugin";(copied/"manifest.json").write_text(json.dumps(data));self.assertTrue(manager.inspect(copied).ok)
 def test_no_external_action_symbols(self):
  source=(SOURCE/"plugin.py").read_text();self.assertNotIn("import subprocess",source);self.assertNotIn("import socket",source);self.assertNotIn("import requests",source)
