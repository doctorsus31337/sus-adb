import json,shutil,tempfile,unittest
from pathlib import Path
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.official_catalog import OfficialPluginCatalog
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
ROOT=Path(__file__).parents[1];OFFICIAL=ROOT/"plugins/official";PID="susadb.skeleton-module"
class T(unittest.TestCase):
 def test_bounded_export_is_deterministic_and_non_mutating(self):
  with tempfile.TemporaryDirectory() as d:
   catalog=OfficialPluginCatalog(OFFICIAL);item=catalog.get(PID);before=item.package_digest;r=catalog.export_template(PID,"export-template",d,before);self.assertTrue(r.ok,r.error);self.assertEqual(r.file_count,9);self.assertGreater(r.total_bytes,0);self.assertEqual(r.source_digest,before);self.assertTrue(all((Path(r.path)/v).is_file() for v in ("manifest.json","plugin.py","README.md","TUTORIAL.md","EXERCISES.md","tests/test_lifecycle.py")));text="".join(p.read_text(encoding="utf-8") for p in Path(r.path).rglob("*") if p.is_file());self.assertNotIn("/"+"home"+"/"+"doctorsus",text);self.assertNotIn("C:"+"\\Users\\",text);self.assertEqual(catalog.get(PID).package_digest,before)
 def test_existing_destination_limits_and_bad_digest_block(self):
  with tempfile.TemporaryDirectory() as d:
   catalog=OfficialPluginCatalog(OFFICIAL);item=catalog.get(PID);(Path(d)/"susadb-skeleton-module").mkdir();self.assertFalse(catalog.export_template(PID,"export-template",d,item.package_digest).ok)
   other=Path(d)/"other";other.mkdir();self.assertFalse(catalog.export_template(PID,"export-template",other,"0"*64).ok);self.assertFalse(catalog.export_template(PID,"export-template",other,item.package_digest,max_files=1).ok);self.assertFalse(catalog.export_template(PID,"export-template",other,item.package_digest,max_bytes=1).ok)
 def test_symlink_and_traversal_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   copied=Path(d)/"official";shutil.copytree(OFFICIAL,copied);skeleton=copied/"skeleton_module";(skeleton/"link.md").symlink_to(skeleton/"README.md");data=json.loads((skeleton/"manifest.json").read_text());action=data["addon_ui"]["catalog_actions"][0];action["include"]=["link.md"];(skeleton/"manifest.json").write_text(json.dumps(data));catalog=OfficialPluginCatalog(copied);self.assertIsNone(catalog.get(PID))
   shutil.rmtree(copied);shutil.copytree(OFFICIAL,copied);skeleton=copied/"skeleton_module";data=json.loads((skeleton/"manifest.json").read_text());data["addon_ui"]["catalog_actions"][0]["include"]=["../outside"];(skeleton/"manifest.json").write_text(json.dumps(data));catalog=OfficialPluginCatalog(copied);item=catalog.get(PID);self.assertFalse(catalog.export_template(PID,"export-template",Path(d)/"out2",item.package_digest).ok)
 def test_unchanged_official_id_cannot_install_as_derivative(self):
  with tempfile.TemporaryDirectory() as d:
   catalog=OfficialPluginCatalog(OFFICIAL);item=catalog.get(PID);export=catalog.export_template(PID,"export-template",d,item.package_digest);store=PluginStore(Path(d)/"store");manager=PluginManager(store,PluginTrustStore(store.root/"state/trust.json"),ContributionRegistry(),official_root=OFFICIAL);result=manager.install(export.path);self.assertFalse(result.ok);self.assertIn("reserved",result.error);self.assertFalse(manager.list())
