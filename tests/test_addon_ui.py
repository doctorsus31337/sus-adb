import json,tempfile,unittest
from pathlib import Path
from app.plugins.addon_presenter import card_actions,card_spec,lifecycle_for
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
 def test_six_independent_cards_and_no_discovery_transition(self):
  with tempfile.TemporaryDirectory() as d:
   manager=self.manager(d);items=manager.official();cards=[card_spec(item,manager) for item in items]
   self.assertEqual(len(cards),6);self.assertEqual(len({v.plugin_id for v in cards}),6);self.assertTrue(all(v.lifecycle_status=="Available" for v in cards));self.assertFalse(manager.list());self.assertFalse(manager.registry.list())
   modes={v.plugin_id:v.preferred_mode.value for v in cards};self.assertEqual(modes["susadb.device-rescue-recovery"],"window");self.assertEqual(modes["susadb.rootability-advisor"],"hybrid");self.assertEqual(modes["susadb.webview-security-inspector"],"hybrid");self.assertEqual(modes["susadb.skeleton-module"],"window")
 def test_lifecycle_is_not_chained(self):
  with tempfile.TemporaryDirectory() as d:
   manager=self.manager(d);item=manager.official()[0];pid=item.manifest.plugin_id
   self.assertTrue(manager.install_official(pid,item.package_digest).ok);self.assertEqual(lifecycle_for(manager,pid),"Permissions Required");self.assertFalse(manager.records[pid][2].enabled);self.assertFalse(manager.registry.list())
 def test_zero_capability_trust_is_distinct_and_explicit(self):
  with tempfile.TemporaryDirectory() as d:
   manager=self.manager(d);item=next(v for v in manager.official() if not v.manifest.requested_capabilities);pid=item.manifest.plugin_id
   self.assertTrue(manager.install_official(pid,item.package_digest).ok);self.assertEqual(lifecycle_for(manager,pid),"Trust Required");actions=card_actions(card_spec(item,manager));self.assertIn("Trust",actions);self.assertNotIn("Permissions",actions);self.assertFalse(manager.trust_zero_capability(pid).ok);self.assertFalse(manager.trust.verify(pid,item.package_digest));self.assertTrue(manager.trust_zero_capability(pid,True).ok);self.assertEqual(lifecycle_for(manager,pid),"Installed");self.assertIn(pid,manager.records);self.assertFalse(manager.records[pid][2].enabled);self.assertFalse(manager.registry.list());self.assertNotIn(pid,manager.loader.statuses)
 def test_export_action_is_present_in_every_skeleton_state(self):
  class Host:
   opened=False
   def is_open(self,_):return self.opened
  with tempfile.TemporaryDirectory() as d:
   manager=self.manager(d);item=next(v for v in manager.official() if v.manifest.plugin_id=="susadb.skeleton-module");pid=item.manifest.plugin_id;host=Host()
   self.assertIn("Export Template…",card_actions(card_spec(item,manager,host)));manager.install_official(pid,item.package_digest);self.assertIn("Export Template…",card_actions(card_spec(item,manager,host)));manager.trust_zero_capability(pid,True);self.assertIn("Export Template…",card_actions(card_spec(item,manager,host)));manager.enable(pid);self.assertIn("Export Template…",card_actions(card_spec(item,manager,host)));manager.load(pid);self.assertIn("Export Template…",card_actions(card_spec(item,manager,host)));host.opened=True;self.assertIn("Export Template…",card_actions(card_spec(item,manager,host)))
 def test_loaded_assistants_are_independently_openable(self):
  with tempfile.TemporaryDirectory() as d:
   manager=self.manager(d)
   for plugin_id in ("susadb.frida-tutorial","susadb.objection-tutorial"):
    item=next(v for v in manager.official() if v.manifest.plugin_id==plugin_id)
    manager.install_official(plugin_id,item.package_digest);manager.approve(plugin_id,item.manifest.requested_capabilities);manager.enable(plugin_id);manager.load(plugin_id)
    spec=card_spec(item,manager);self.assertTrue(spec.openable);self.assertEqual(card_actions(spec),("Details","Open","Unload"))
 def test_official_assistant_update_requires_review_and_new_digest_trust(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);official=root/"official"/"assistant";old=root/"old";store=PluginStore(root/"store")
   for path,version,name in ((official,"1.1.0","Frida Assistant"),(old,"1.0.0","Frida Foundations")):
    path.mkdir(parents=True);(path/"manifest.json").write_text(json.dumps({"plugin_id":"susadb.frida-tutorial","name":name,"version":version,"minimum_sus_adb_version":"1.0.0","entry_point":"plugin.py:Plugin","requested_capabilities":["read-selected-device","read-selected-target"],"contributed_components":[],"enabled":False}),encoding="utf-8");(path/"plugin.py").write_text("class Plugin:\n def activate(self,api): return ()\n def deactivate(self): pass\n",encoding="utf-8")
   self.assertTrue(store.install(old).ok)
   manager=PluginManager(store,PluginTrustStore(store.root/"state/trust.json"),ContributionRegistry(),official_root=root/"official")
   old_digest=manager.records["susadb.frida-tutorial"][1].package_digest;manager.trust.approve("susadb.frida-tutorial",old_digest,("read-selected-device","read-selected-target"));manager.refresh()
   item=manager.official()[0];self.assertEqual(lifecycle_for(manager,item.manifest.plugin_id),"Update Available");self.assertFalse(manager.update_official(item.manifest.plugin_id,item.package_digest).ok);self.assertTrue(manager.update_official(item.manifest.plugin_id,item.package_digest,True).ok)
   record=manager.records[item.manifest.plugin_id];self.assertEqual(record[2].version,"1.1.0");self.assertFalse(record[2].enabled);self.assertFalse(manager.trust.verify(item.manifest.plugin_id,record[1].package_digest));self.assertEqual(lifecycle_for(manager,item.manifest.plugin_id),"Permissions Required")
 def test_warning_contract(self):
  source=(ROOT/"app/gui/pentest_workspace.py").read_text(encoding="utf-8");self.assertIn('"Authorization must be explicitly confirmed."',source);self.assertNotIn('"Authorization must be explicitly confirm"',source)
 def test_generic_hosts_have_no_official_ids_or_raw_root_provider(self):
  text="".join((ROOT/path).read_text(encoding="utf-8") for path in ("app/gui/addons_center.py","app/gui/addon_window_host.py","app/gui/menu_bar.py"));self.assertNotIn("susadb.",text);self.assertNotIn("import subprocess",text);self.assertNotIn("import requests",text)
