import json,tempfile,unittest
from pathlib import Path
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.plugin_loader import PluginLoader,LoaderState
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_trust import PluginTrustStore
from app.plugins.plugin_validator import PluginValidator
class T(unittest.TestCase):
 def package(self,root,body):
  root.mkdir();(root/"manifest.json").write_text(json.dumps({"plugin_id":"demo","name":"D","version":"1.0.0","entry_point":"plugin.py:Plugin"}));(root/"plugin.py").write_text(body);return PluginPackage.inspect(root)
 def test_untrusted_no_load_lifecycle_and_failure_containment(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"p";i=self.package(root,"class Plugin:\n def activate(self,api): return ({'contribution_id':'c','contribution_type':'parser','title':'C'},)\n def deactivate(self): pass\n");reg=ContributionRegistry();trust=PluginTrustStore(Path(d)/"trust.json");loader=PluginLoader(reg,PluginValidator(),trust,lambda m:object());self.assertEqual(loader.load(root,i).state,LoaderState.DISABLED);self.assertEqual(loader.load(root,i,enabled=True).state,LoaderState.BLOCKED);trust.approve("demo",i.package_digest);self.assertEqual(loader.load(root,i,enabled=True).state,LoaderState.ACTIVE);self.assertEqual(len(reg.list()),1);self.assertEqual(loader.unload("demo").state,LoaderState.UNLOADED);self.assertFalse(reg.list())
