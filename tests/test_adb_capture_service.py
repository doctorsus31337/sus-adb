import tempfile,unittest
from pathlib import Path
from app.core.adb_capture_service import ADBCaptureService
from app.core.command_result import CommandResult
class ADB:
 adb_path="adb"
 def __init__(self):self.calls=[]
 def run(self,*a,serial=None):
  self.calls.append((a,serial))
  if a and a[0]=="pull":Path(a[2]).write_bytes(b"capture")
  return CommandResult(a,0,"ok")
class Process:
 def __init__(self):self.stopped=False
 def wait(self,timeout=None):return 0
 def terminate(self):self.stopped=True
 def kill(self):self.stopped=True
class Session:
 def permits(self,c):return c=="evidence-collection"
class CaptureTests(unittest.TestCase):
 def test_screenshot_pull_cleanup_hash_serial(self):
  with tempfile.TemporaryDirectory() as d:
   adb=ADB();dest=Path(d)/"shot.png";r=ADBCaptureService(adb,lambda a:Process(),session_provider=lambda:Session()).screenshot("SER",dest,"p",confirmed=True);self.assertTrue(r.ok);self.assertEqual(len(r.value.sha256),64);self.assertTrue(all(c[1]=="SER" for c in adb.calls));self.assertIn("rm",adb.calls[-1][0])
 def test_recording_limit_start_finish_and_stop(self):
  with tempfile.TemporaryDirectory() as d:
   adb=ADB();p=Process();service=ADBCaptureService(adb,lambda a:p,max_duration=20,session_provider=lambda:Session());self.assertFalse(service.start_recording("S",Path(d)/"x.mp4",21,confirmed=True).ok);started=service.start_recording("S",Path(d)/"x.mp4",5,"p",confirmed=True);self.assertTrue(started.ok);done=service.finish_recording(started.value);self.assertTrue(done.ok);service.stop_recording();self.assertTrue(p.stopped)
 def test_missing_serial_and_factory_failure(self):
  service=ADBCaptureService(ADB(),lambda a:(_ for _ in ()).throw(OSError("unsupported")),session_provider=lambda:Session());self.assertFalse(service.screenshot("","x").ok);self.assertIn("unsupported",service.start_recording("S","x",5,confirmed=True).error)
 def test_scope_and_confirmation_required(self):
  service=ADBCaptureService(ADB(),lambda a:Process());self.assertIn("scope",service.screenshot("S","x",confirmed=True).error);service=ADBCaptureService(ADB(),lambda a:Process(),session_provider=lambda:Session());self.assertIn("confirmation",service.screenshot("S","x").error)

if __name__=="__main__":unittest.main()
