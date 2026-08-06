import json,tempfile,unittest
from pathlib import Path
from unittest import mock

from app.plugins.addon_presenter import card_actions,card_spec,lifecycle_for
from app.plugins.contribution_registry import Contribution,ContributionRegistry
from app.plugins.plugin_loader import LoaderState,LoaderStatus
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore

PID="demo.official"

class WindowHost:
 def __init__(self,opened=False):self.opened=opened
 def is_open(self,_contribution_id):return self.opened

class T(unittest.TestCase):
 def package(self,path,version,marker="old",capabilities=("read-selected-device",),description="Installed description",ui_mode="window"):
  path.mkdir(parents=True,exist_ok=True)
  manifest={"plugin_id":PID,"name":"Official Demo","version":version,"description":description,"author":"SUS Companion","entry_point":"plugin.py:Plugin","requested_capabilities":list(capabilities),"contributed_components":[{"contribution_id":"demo.panel","contribution_type":"pentest-panel","title":"Demo Panel","factory":"panel_spec","metadata":{"ui_mode":ui_mode}}],"addon_ui":{"ui_mode":ui_mode},"enabled":False}
  (path/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
  (path/"plugin.py").write_text(f"MARKER={marker!r}\nclass Plugin:\n def activate(self,api): return ()\n def deactivate(self): pass\n",encoding="utf-8")
  return path
 def fixture(self,d,candidate_version="1.1.0",candidate_marker="new",candidate_capabilities=("read-selected-device","read-selected-target")):
  root=Path(d);old=self.package(root/"old","1.0.0");candidate=self.package(root/"official"/"demo",candidate_version,candidate_marker,candidate_capabilities,"Candidate description","hybrid")
  store=PluginStore(root/"store");self.assertTrue(store.install(old).ok)
  trust=PluginTrustStore(store.root/"state"/"trust.json");manager=PluginManager(store,trust,ContributionRegistry(),official_root=root/"official")
  old_digest=manager.records[PID][1].package_digest;trust.approve(PID,old_digest,("read-selected-device",));manager.refresh()
  return root,candidate,store,trust,manager
 def test_update_is_additional_to_installed_lifecycle_and_review_is_read_only(self):
  with tempfile.TemporaryDirectory() as d:
   _root,_candidate,store,_trust,manager=self.fixture(d);item=manager.official()[0];record=manager.records[PID];state_before=store.state(PID).copy()
   spec=card_spec(item,manager);self.assertEqual(spec.version,"1.0.0");self.assertEqual(lifecycle_for(manager,PID),"Installed");self.assertTrue(spec.update_available);self.assertIn("Enable",card_actions(spec));self.assertIn("Review Update",card_actions(spec));self.assertNotIn("Install Update",card_actions(spec))
   review=manager.official_update_review(PID,item.package_digest);self.assertTrue(review.ok);self.assertEqual(manager.records[PID][0],record[0]);self.assertEqual(store.state(PID),state_before);self.assertEqual(review.status.installed_version,"1.0.0");self.assertEqual(review.status.candidate_version,"1.1.0");self.assertEqual(review.status.capability_additions,("read-selected-target",));self.assertTrue(review.status.presentation_changes);self.assertTrue(review.status.executable_files_changed);self.assertTrue(review.status.version_changed)
 def test_review_is_exact_digest_bound_and_persists_across_manager_reopen(self):
  with tempfile.TemporaryDirectory() as d:
   root,candidate,store,trust,manager=self.fixture(d);item=manager.official()[0]
   self.assertTrue(manager.mark_official_update_reviewed(PID,item.package_digest).ok);self.assertTrue(manager.official_update_reviewed(PID,item.package_digest));self.assertIn("Install Update",card_actions(card_spec(item,manager)))
   reopened=PluginManager(store,PluginTrustStore(trust.path),ContributionRegistry(),official_root=root/"official");self.assertTrue(reopened.official_update_reviewed(PID,item.package_digest))
   (candidate/"plugin.py").write_text((candidate/"plugin.py").read_text(encoding="utf-8")+"\nCHANGED=True\n",encoding="utf-8")
   changed=reopened.official()[0];self.assertNotEqual(changed.package_digest,item.package_digest);self.assertFalse(reopened.official_update_reviewed(PID,changed.package_digest));self.assertNotIn("Install Update",card_actions(card_spec(changed,reopened)))
 def test_load_path_and_card_use_installed_package_not_candidate(self):
  with tempfile.TemporaryDirectory() as d:
   _root,_candidate,_store,_trust,manager=self.fixture(d);item=manager.official()[0];old_path,old_inspection,_manifest=manager.records[PID]
   self.assertTrue(manager.enable(PID).ok);captured={}
   def fake_load(path,inspection,enabled=False):captured.update(path=path,digest=inspection.package_digest,enabled=enabled);return LoaderStatus(PID,LoaderState.ACTIVE)
   with mock.patch.object(manager.loader,"load",side_effect=fake_load):self.assertTrue(manager.load(PID).ok)
   self.assertEqual(Path(captured["path"]),old_path);self.assertEqual(captured["digest"],old_inspection.package_digest);self.assertNotEqual(captured["digest"],item.package_digest)
 def test_loaded_or_open_addon_requires_explicit_unload_and_keeps_review(self):
  with tempfile.TemporaryDirectory() as d:
   _root,_candidate,_store,_trust,manager=self.fixture(d);item=manager.official()[0];self.assertTrue(manager.mark_official_update_reviewed(PID,item.package_digest).ok);self.assertTrue(manager.enable(PID).ok)
   manager.loader.statuses[PID]=LoaderStatus(PID,LoaderState.ACTIVE);manager.loader.instances[PID]=object();manager.registry.register(PID,(Contribution("demo.panel","pentest-panel","Demo",PID),))
   opened=card_spec(item,manager,WindowHost(True));self.assertEqual(opened.lifecycle_status,"Window Open");self.assertIn("Unload",card_actions(opened));self.assertNotIn("Install Update",card_actions(opened));self.assertIn("unload add-on",opened.update_status)
   self.assertFalse(manager.install_official_update(PID,item.package_digest).ok);self.assertTrue(manager.official_update_reviewed(PID,item.package_digest))
   self.assertTrue(manager.unload(PID).ok);self.assertFalse(manager.registry.by_plugin(PID));ready=card_spec(item,manager,WindowHost(False));self.assertIn("Install Update",card_actions(ready));self.assertTrue(manager.official_update_reviewed(PID,item.package_digest))
 def test_successful_update_is_atomic_disabled_untrusted_and_needs_no_restart(self):
  with tempfile.TemporaryDirectory() as d:
   root,_candidate,store,trust,manager=self.fixture(d);item=manager.official()[0];old_digest=manager.records[PID][1].package_digest
   self.assertTrue(manager.mark_official_update_reviewed(PID,item.package_digest).ok);result=manager.install_official_update(PID,item.package_digest);self.assertTrue(result.ok,result.error)
   record=manager.records[PID];self.assertEqual(record[2].version,"1.1.0");self.assertEqual(record[1].package_digest,item.package_digest);self.assertFalse(record[2].enabled);self.assertFalse(trust.verify(PID,old_digest));self.assertFalse(trust.verify(PID,item.package_digest));self.assertEqual(trust.approved(PID,item.package_digest),());self.assertFalse(manager.registry.by_plugin(PID));self.assertEqual(len(tuple((store.root/"disabled"/PID).iterdir())),1)
   spec=card_spec(manager.official()[0],manager);self.assertEqual(spec.lifecycle_status,"Permissions Required");self.assertEqual(spec.update_status,"Update installed.\nReview and approve this package’s new exact digest before enabling it.");self.assertIn("Review Permissions",card_actions(spec));self.assertNotIn("Review Update",card_actions(spec));self.assertNotIn("Install Update",card_actions(spec))
   reopened=PluginManager(store,PluginTrustStore(trust.path),ContributionRegistry(),official_root=root/"official");reopened_spec=card_spec(reopened.official()[0],reopened);self.assertEqual(reopened.records[PID][2].version,"1.1.0");self.assertEqual(reopened_spec.lifecycle_status,"Permissions Required");self.assertIn("Review Permissions",card_actions(reopened_spec));self.assertFalse(reopened_spec.update_available)
   self.assertTrue(manager.approve(PID,manager.records[PID][2].requested_capabilities).ok);self.assertEqual(card_actions(card_spec(manager.official()[0],manager)),("Details","Enable"));self.assertFalse(manager.post_update_activation_pending(PID))
   self.assertTrue(manager.enable(PID).ok);self.assertEqual(card_actions(card_spec(manager.official()[0],manager)),("Details","Load"))
   def fake_load(path,inspection,enabled=False):
    status=LoaderStatus(PID,LoaderState.ACTIVE);manager.loader.statuses[PID]=status;return status
   with mock.patch.object(manager.loader,"load",side_effect=fake_load):self.assertTrue(manager.load(PID).ok)
   self.assertEqual(card_actions(card_spec(manager.official()[0],manager)),("Details","Open","Unload"))
 def test_validation_copy_and_replacement_failures_preserve_usable_old_package(self):
  with tempfile.TemporaryDirectory() as d:
   _root,candidate,store,trust,manager=self.fixture(d);item=manager.official()[0];old_path,old_inspection,_manifest=manager.records[PID];self.assertTrue(manager.mark_official_update_reviewed(PID,item.package_digest).ok)
   with mock.patch("app.plugins.plugin_store.shutil.copytree",side_effect=OSError("copy failed")):
    result=manager.install_official_update(PID,item.package_digest)
   self.assertFalse(result.ok);self.assertEqual(PluginPackage.inspect(old_path).package_digest,old_inspection.package_digest);self.assertTrue(trust.verify(PID,old_inspection.package_digest))
   original=store._replace_path;calls=[]
   def fail_second(source,destination):
    calls.append((Path(source),Path(destination)))
    if len(calls)==2:raise OSError("replacement failed")
    return original(source,destination)
   with mock.patch.object(store,"_replace_path",side_effect=fail_second):
    result=manager.install_official_update(PID,item.package_digest)
   self.assertFalse(result.ok);self.assertTrue(old_path.exists());self.assertEqual(PluginPackage.inspect(old_path).package_digest,old_inspection.package_digest);self.assertTrue(trust.verify(PID,old_inspection.package_digest));self.assertEqual(manager.records[PID][1].package_digest,old_inspection.package_digest)
   (candidate/"manifest.json").write_text("{}",encoding="utf-8");self.assertFalse(manager.official_update_review(PID).ok);self.assertTrue(old_path.exists())
 def test_same_digest_has_no_update_and_same_version_changed_digest_is_warned_and_installable(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);official=self.package(root/"official"/"demo","1.0.0");store=PluginStore(root/"store");trust=PluginTrustStore(store.root/"state"/"trust.json");manager=PluginManager(store,trust,ContributionRegistry(),official_root=root/"official");item=manager.official()[0]
   self.assertTrue(manager.install_official(PID,item.package_digest).ok);manager.refresh();same=manager.official()[0];self.assertFalse(card_spec(same,manager).update_available);self.assertFalse(manager.official_update_review(PID,same.package_digest).ok)
  with tempfile.TemporaryDirectory() as d:
   _root,_candidate,_store,_trust,manager=self.fixture(d,candidate_version="1.0.0");item=manager.official()[0];spec=card_spec(item,manager);self.assertIn("Package contents changed without a version change",spec.update_status)
   review=manager.official_update_review(PID,item.package_digest);self.assertTrue(review.status.digest_only_changed);self.assertTrue(manager.mark_official_update_reviewed(PID,item.package_digest).ok);self.assertTrue(manager.install_official_update(PID,item.package_digest).ok)
