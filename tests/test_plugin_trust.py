import tempfile,unittest
from pathlib import Path
from app.plugins.plugin_trust import PluginTrustStore
class T(unittest.TestCase):
 def test_digest_bound_revoke(self):
  with tempfile.TemporaryDirectory() as d:
   t=PluginTrustStore(Path(d)/"trust.json");t.approve("p","abc",("read-selected-device",));self.assertTrue(t.verify("p","abc"));self.assertFalse(t.verify("p","changed"));t.revoke("p");self.assertFalse(t.verify("p","abc"))
