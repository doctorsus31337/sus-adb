import json,tempfile,unittest
from pathlib import Path
from app.core.config_manager import ConfigManager
from app.core.config_schema import defaults
class ConfigManagerTests(unittest.TestCase):
 def test_atomic_round_trip_and_unknown_key(self):
  with tempfile.TemporaryDirectory() as d:
   m=ConfigManager(d);data=defaults();data["extension"]={"kept":True};self.assertTrue(m.save(data).ok);loaded=m.load().data;self.assertTrue(loaded["extension"]["kept"]);self.assertFalse(loaded["script_studio"]["show_static_analysis_advisories"])
 def test_malformed_is_quarantined(self):
  with tempfile.TemporaryDirectory() as d:
   m=ConfigManager(d);m.path.write_text("{");result=m.load();self.assertTrue(result.ok);self.assertTrue((Path(d)/"config.malformed.json").exists())
 def test_platform_paths(self):
  self.assertIn("SUS-ADB",str(ConfigManager.resolve_directory("nt",{"APPDATA":"C:/Users/Test/AppData"})))
  self.assertEqual(str(ConfigManager.resolve_directory("posix",{"XDG_CONFIG_HOME":"/tmp/config"})),"/tmp/config/sus-adb")
  self.assertNotIn("sus-companion",str(ConfigManager.resolve_directory("posix",{"XDG_CONFIG_HOME":"/tmp/config"})))
 def test_nested_secrets_rejected_and_quarantines_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   m=ConfigManager(d);data=defaults();data["plugin"]={"token":"nope"};self.assertFalse(m.save(data).ok)
   m.path.write_text("{");m.load();m.path.write_text("{");m.load();self.assertTrue((Path(d)/"config.malformed.json").exists());self.assertTrue((Path(d)/"config.malformed.1.json").exists())
if __name__=="__main__":unittest.main()
