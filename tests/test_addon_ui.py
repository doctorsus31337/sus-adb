import tempfile,unittest
from pathlib import Path
from app.plugins.addon_presenter import card_spec,lifecycle_for
from app.plugins.plugin_ui import AddonUIMode,AddonWindowSpec,PluginPanelSpec,resolve_ui_mode,clamp_addon_geometry
from app.plugins.official_catalog import OfficialPluginCatalog
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
from app.plugins.contribution_registry import ContributionRegistry
ROOT=Path(__file__).parents[1]
class T(unittest.TestCase):
 def manager(self,d):
  store=PluginStore(Path(d)/"store");return PluginManager(store,PluginTrustStore(store.root/"state/trust.json"),ContributionRegistry(),official_root=ROOT/"plugins/official")
 def test_modes_and_safe_geometry(self):
  panel=PluginPanelSpec("x",());spec=AddonWindowSpec("id","Title",panel,AddonUIMode.HYBRID,1000,700,800,500)
  self.assertEqual(resolve_ui_mode("embedded"),AddonUIMode.EMBEDDED);self.assertEqual(resolve_ui_mode("bad"),AddonUIMode.WINDOW)
  self.assertEqual(clamp_addon_geometry("bad",1200,800,spec),"1000x700+100+50")
  self.assertEqual(clamp_addon_geometry("1000x700+5000+5000",1200,800,spec),"1000x700+200+100")
 def test_four_independent_cards_and_no_discovery_transition(self):
  with tempfile.TemporaryDirectory() as d:
   manager=self.manager(d);items=manager.official();cards=[card_spec(item,manager) for item in items]
   self.assertEqual(len(cards),4);self.assertEqual(len({v.plugin_id for v in cards}),4);self.assertTrue(all(v.lifecycle_status=="Available" for v in cards));self.assertFalse(manager.list());self.assertFalse(manager.registry.list())
   modes={v.plugin_id:v.preferred_mode.value for v in cards};self.assertEqual(modes["susadb.device-rescue-recovery"],"window");self.assertEqual(modes["susadb.rootability-advisor"],"hybrid");self.assertEqual(modes["susadb.webview-security-inspector"],"hybrid");self.assertEqual(modes["susadb.skeleton-module"],"window")
 def test_lifecycle_is_not_chained(self):
  with tempfile.TemporaryDirectory() as d:
   manager=self.manager(d);item=manager.official()[0];pid=item.manifest.plugin_id
   self.assertTrue(manager.install_official(pid,item.package_digest).ok);self.assertEqual(lifecycle_for(manager,pid),"Permissions Required");self.assertFalse(manager.records[pid][2].enabled);self.assertFalse(manager.registry.list())
 def test_warning_contract(self):
  source=(ROOT/"app/gui/pentest_workspace.py").read_text(encoding="utf-8");self.assertIn('"Authorization must be explicitly confirmed."',source);self.assertNotIn('"Authorization must be explicitly confirm"',source)
 def test_generic_hosts_have_no_official_ids_or_raw_root_provider(self):
  text="".join((ROOT/path).read_text(encoding="utf-8") for path in ("app/gui/addons_center.py","app/gui/addon_window_host.py","app/gui/menu_bar.py"));self.assertNotIn("susadb.",text);self.assertNotIn("subprocess",text);self.assertNotIn("requests",text)
