import unittest
from app.plugins.plugin_manifest import *
class T(unittest.TestCase):
 def test_deterministic_semver_paths(self):
  m=PluginManifest("demo.local","Demo","1.2.3",entry_point="plugin.py:Plugin",installation_timestamp="t",modified_timestamp="t");self.assertEqual(PluginManifest.from_dict(m.to_dict()),m);self.assertEqual(m.computed_manifest_digest(),m.computed_manifest_digest());self.assertRaises(ValueError,PluginManifest,"Bad ID","x","1");self.assertRaises(ValueError,PluginManifest,"bad","x","1.0.0",entry_point="../x.py:Plugin")
