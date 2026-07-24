import json,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from app.plugins.plugin_trust import PluginTrustStore
from official_plugin_helpers import load
M=load("official_rootability","rootability_advisor")
class T(unittest.TestCase):
 def test_identity_boot_root_slot_and_unknown_parsing(self):
  raw="[ro.product.device]: [lynx]\n[ro.boot.verifiedbootstate]: [green]\n[ro.boot.slot_suffix]: [_a]\n[ro.boot.dynamic_partitions]: [true]";identity=M.parse_properties(raw);self.assertEqual(identity["codename"],"lynx");boot=M.parse_boot_state({**identity,"ro.boot.flash.locked":"1","root":"uid=0","magisk":"present"});self.assertTrue(boot["locked"]);self.assertEqual(boot["slot"],"_a");self.assertEqual(M.parse_boot_state({})["verified_boot"],"unknown")
 def test_safe_firmware_hash_match_mismatch_and_traversal(self):
  with tempfile.TemporaryDirectory() as d:
   good=Path(d)/"factory.zip"
   with zipfile.ZipFile(good,"w") as z:z.writestr("android-info.txt","require product=lynx\n")
   self.assertEqual(M.inspect_firmware(good,"lynx").classification,"compatible");self.assertEqual(M.inspect_firmware(good,"other").classification,"dangerous mismatch");self.assertEqual(len(M.inspect_firmware(good).sha256),64)
   bad=Path(d)/"bad.zip"
   with zipfile.ZipFile(bad,"w") as z:z.writestr("../escape","x")
   self.assertRaises(ValueError,M.inspect_firmware,bad,"lynx")
 def test_readiness_recovery_warning_and_preview_only(self):
  matrix=M.readiness({"codename":"x"},{"locked":True,"verified_boot":"unknown"},True);self.assertTrue(matrix.blockers);self.assertTrue(matrix.data_wipe_likely);self.assertIn("preview only",matrix.command_previews[-1]);source=Path(M.__file__).read_text();self.assertNotIn("subprocess",source);self.assertNotIn("shell=True",source)
 def test_stable_id_new_name_views_and_host_owned_workspace(self):
  manifest=json.loads((Path(M.__file__).parent/"manifest.json").read_text())
  self.assertEqual(manifest["plugin_id"],"susadb.rootability-advisor")
  self.assertEqual(manifest["name"],"Instrumentation & Root Readiness Advisor")
  self.assertEqual(manifest["version"],"0.2.0")
  panel=M.panel_spec(SimpleNamespace(selected_device={"serial":"S","state":"device","root_available":True},adb_state="device"))
  self.assertEqual(tuple(v.name for v in panel.views),("Overview","Device Identity","Root & Boot Chain","Frida Routes","Frida Server Setup","Gadget Readiness","Firmware Inputs","Compatibility","Plan"))
  metadata=manifest["contributed_components"][1]["metadata"]
  self.assertEqual(metadata["workspace_kind"],"readiness-advisor")
  self.assertTrue(metadata["device_selector"])
 def test_changed_digest_requires_explicit_retrust(self):
  with tempfile.TemporaryDirectory() as d:
   store=PluginTrustStore(Path(d)/"trust.json")
   store.approve("susadb.rootability-advisor","a"*64,("read-selected-device",))
   self.assertTrue(store.verify("susadb.rootability-advisor","a"*64))
   self.assertFalse(store.verify("susadb.rootability-advisor","b"*64))
