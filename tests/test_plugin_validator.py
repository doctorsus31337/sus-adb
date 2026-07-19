import json,tempfile,unittest
from pathlib import Path
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_validator import PluginValidator
class T(unittest.TestCase):
 def test_static_errors_warnings_cautions(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/"manifest.json").write_text(json.dumps({"plugin_id":"demo","name":"D","version":"1.0.0","requested_capabilities":["access-network"],"contributed_components":[]}));(p/"plugin.py").write_text("raise Exception('not imported')")
   i=PluginPackage.inspect(p);v=PluginValidator().validate(i);self.assertTrue(v.valid);self.assertTrue(v.capability_cautions);self.assertTrue(PluginValidator().validate(i,existing_ids=("demo",)).errors)
