import json,tempfile,unittest
from pathlib import Path
from app.core.config_manager import ConfigManager
from app.core.config_schema import defaults
class ConfigManagerTests(unittest.TestCase):
 def test_atomic_round_trip_and_unknown_key(self):
  with tempfile.TemporaryDirectory() as d:
   m=ConfigManager(d);data=defaults();data["extension"]={"kept":True};self.assertTrue(m.save(data).ok);self.assertTrue(m.load().data["extension"]["kept"])
 def test_malformed_is_quarantined(self):
  with tempfile.TemporaryDirectory() as d:
   m=ConfigManager(d);m.path.write_text("{");result=m.load();self.assertTrue(result.ok);self.assertTrue((Path(d)/"config.malformed.json").exists())
 def test_platform_paths(self):
  self.assertIn("SUS-ADB",str(ConfigManager.resolve_directory("nt",{"APPDATA":"C:/Users/Test/AppData"})))
  self.assertEqual(str(ConfigManager.resolve_directory("posix",{"XDG_CONFIG_HOME":"/tmp/config"})),"/tmp/config/sus-adb")
if __name__=="__main__":unittest.main()
