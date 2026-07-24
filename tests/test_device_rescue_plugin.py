import json,tempfile,unittest
from pathlib import Path
from official_plugin_helpers import load
M=load("official_device_rescue","device_rescue_recovery")
class Session:
 def __init__(self,allowed=True):self.allowed=allowed
 def permits(self,value):return self.allowed and value in {"sensitive-data-inspection","storage-inspection"}
class T(unittest.TestCase):
 def test_states_presets_and_private_gate(self):
  self.assertEqual(len(M.public_paths()),10);self.assertIn("/sdcard/Android/media",M.public_paths());self.assertIn("authorization",M.classify_access("unauthorized"));self.assertIn("Recovery ADB",M.classify_access("recovery",True));self.assertIn("wipe data",M.classify_access("bootloader"));self.assertFalse(M.private_path_allowed("/data/data/app",False,Session(),True));self.assertFalse(M.private_path_allowed("/data/data/app",True,Session(False),True));self.assertTrue(M.private_path_allowed("/data/data/app",True,Session(),True))
 def test_copy_limits_duplicates_resume_cancel_hash_and_manifest(self):
  records=[("/sdcard/DCIM/a.jpg",b"abc","1"),("/sdcard/DCIM/b.jpg",b"defg","2")]
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);engine=M.RecoveryEngine(lambda serial,path,depth:records)
   limited=engine.recover("SERIAL",("/sdcard/DCIM",),root,M.RecoveryLimits(1,99,2,1));self.assertFalse(limited.ok)
   result=engine.recover("SERIAL",("/sdcard/DCIM",),root);self.assertTrue(result.ok);self.assertEqual(len(result.items),2);self.assertTrue(all(len(v.sha256)==64 for v in result.items));text=M.manifest(result.items);self.assertEqual(text,M.manifest(tuple(reversed(result.items))));self.assertEqual(len(json.loads(text)),2)
   skipped=engine.recover("SERIAL",("/sdcard/DCIM",),root,duplicate="skip");self.assertTrue(all(v.state=="skipped" for v in skipped.items));renamed=engine.recover("SERIAL",("/sdcard/DCIM",),root,duplicate="rename");self.assertTrue(renamed.ok);self.assertTrue(engine.recover("SERIAL",("x",),root,cancelled=lambda:True).cancelled);self.assertTrue(engine.recover("SERIAL",("x",),root,resume=result.items).ok)
 def test_explicit_serial_destination_and_no_bypass_surface(self):
  with tempfile.TemporaryDirectory() as d:self.assertFalse(M.RecoveryEngine(lambda *_:()).recover("",(),d).ok)
  source=Path(M.__file__).read_text().casefold();self.assertNotIn("frp bypass",source);self.assertNotIn("unlock bootloader",source);self.assertNotIn("shell=true",source)
