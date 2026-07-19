import unittest
from app.core.adb_explorer_models import *

class ExplorerModelTests(unittest.TestCase):
 def test_package_roundtrip_and_identifier(self):
  p=PackageRecord("com.example.long",label="Example",apk_paths=("/base.apk","/split.apk"),serial="SER")
  self.assertEqual(PackageRecord.from_dict(p.to_dict()).identifier,"com.example.long");self.assertIn("com.example.long",p.display_label)
 def test_component_remote_and_capture_labels(self):
  c=ComponentRecord(ComponentType.ACTIVITY,"com.x",".Main",exported=True);self.assertEqual(c.component_name,"com.x/.Main");self.assertEqual(ComponentRecord.from_dict(c.to_dict()).component_type,ComponentType.ACTIVITY)
  f=RemoteFileEntry("a b","/sdcard/a b",RemoteEntryType.FILE,7,access_method=AccessMethod.ROOT);self.assertEqual(RemoteFileEntry.from_dict(f.to_dict()).remote_path,"/sdcard/a b")
  a=CaptureArtifact(CaptureType.SCREENSHOT,"/tmp/a.png",sha256="a"*64);self.assertIn("screenshot",a.display_label)
 def test_logcat_serialization(self):
  e=LogcatEvent("01-01 00:00:00.000",1,2,"I","Tag","hello","raw","S","p");self.assertEqual(LogcatEvent.from_dict(e.to_dict()).pid,1)

if __name__=="__main__":unittest.main()
