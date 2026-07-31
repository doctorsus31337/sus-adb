import json,tempfile,unittest
from pathlib import Path
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_validator import PluginValidator
class T(unittest.TestCase):
 def test_static_errors_warnings_cautions(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/"manifest.json").write_text(json.dumps({"plugin_id":"demo","name":"D","version":"1.0.0","requested_capabilities":["access-network"],"contributed_components":[]}));(p/"plugin.py").write_text("raise Exception('not imported')")
   i=PluginPackage.inspect(p);v=PluginValidator().validate(i);self.assertTrue(v.valid);self.assertTrue(v.capability_cautions);self.assertTrue(PluginValidator().validate(i,existing_ids=("demo",)).errors)
 def test_log_privacy_capability_has_a_specific_caution(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/"manifest.json").write_text(json.dumps({"plugin_id":"logs","name":"Logs","version":"0.1.0","requested_capabilities":["read-selected-device","read-device-logs"],"contributed_components":[]}));(p/"plugin.py").write_text("class Plugin: pass")
   validation=PluginValidator().validate(PluginPackage.inspect(p));self.assertTrue(validation.valid);self.assertTrue(any("account information" in value for value in validation.capability_cautions))
