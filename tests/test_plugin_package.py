import json,tempfile,unittest,zipfile
from pathlib import Path
from app.plugins.plugin_package import PluginPackage
class T(unittest.TestCase):
 def test_inspect_deterministic_and_archive_traversal(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"p";root.mkdir();(root/"manifest.json").write_text(json.dumps({"plugin_id":"demo","name":"D","version":"1.0.0"}));(root/"plugin.py").write_text("raise Exception('must not execute')")
   a=PluginPackage.inspect(root);b=PluginPackage.inspect(root);self.assertTrue(a.ok);self.assertEqual(a.package_digest,b.package_digest)
   z=Path(d)/"bad.zip"
   with zipfile.ZipFile(z,"w") as f:f.writestr("../escape","x");f.writestr("manifest.json","{}")
   self.assertFalse(PluginPackage.inspect(z).ok)
 def test_harmless_example_is_disabled_and_static(self):
  result=PluginPackage.inspect("plugins/examples/hello_plugin");self.assertTrue(result.ok);self.assertFalse(result.manifest.enabled);self.assertEqual(result.manifest.trust_state.value,"untrusted");self.assertFalse({"access-network","access-host-processes","modify-device-state"}&set(result.manifest.requested_capabilities))
