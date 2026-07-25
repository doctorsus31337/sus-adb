import tempfile,unittest
from pathlib import Path
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.official_catalog import OfficialPluginCatalog
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
ROOT=Path(__file__).parents[1];OFFICIAL=ROOT/"plugins/official"
class T(unittest.TestCase):
 def manager(self,d):
  store=PluginStore(Path(d)/"local");return PluginManager(store,PluginTrustStore(store.root/"state/trust.json"),ContributionRegistry(),official_root=OFFICIAL)
 def test_six_valid_deterministic_inactive_catalog_items(self):
  a=OfficialPluginCatalog(OFFICIAL).list();b=OfficialPluginCatalog(OFFICIAL).list();self.assertEqual(len(a),6);self.assertTrue(all(v.valid and not v.installed and not v.manifest.enabled for v in a));self.assertEqual([v.package_digest for v in a],[v.package_digest for v in b])
 def test_install_trust_enable_load_unload_uninstall_are_separate(self):
  with tempfile.TemporaryDirectory() as d:
   m=self.manager(d);item=m.official()[0];self.assertFalse(m.list());self.assertTrue(m.install_official(item.manifest.plugin_id,item.package_digest).ok);self.assertFalse(m.records[item.manifest.plugin_id][2].enabled);self.assertFalse(m.load(item.manifest.plugin_id).ok);self.assertTrue(m.trust_zero_capability(item.manifest.plugin_id,True).ok if not item.manifest.requested_capabilities else m.approve(item.manifest.plugin_id,item.manifest.requested_capabilities,True).ok);self.assertTrue(m.enable(item.manifest.plugin_id).ok);self.assertFalse(m.registry.list());self.assertTrue(m.load(item.manifest.plugin_id).ok);self.assertTrue(m.unload(item.manifest.plugin_id).ok);self.assertFalse(m.registry.list());self.assertTrue(m.uninstall(item.manifest.plugin_id,True).ok)
 def test_digest_revalidated_before_install(self):
  with tempfile.TemporaryDirectory() as d:
   m=self.manager(d);item=m.official()[0];self.assertFalse(m.install_official(item.manifest.plugin_id,"0"*64).ok);self.assertFalse(m.list())
