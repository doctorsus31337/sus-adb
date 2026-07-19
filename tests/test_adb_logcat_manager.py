import io,unittest
from app.core.adb_logcat_manager import ADBLogcatManager,LogcatState
from app.core.command_result import CommandResult
class ADB:
 adb_path="adb"
 def __init__(self):self.calls=[]
 def run(self,*a,serial=None):self.calls.append((a,serial));return CommandResult(a,0,"")
class Process:
 def __init__(self,lines):self.stdout=iter(lines);self.terminated=False
 def terminate(self):self.terminated=True
 def wait(self,timeout=None):return 0
 def kill(self):self.terminated=True
class LogcatTests(unittest.TestCase):
 LINE="07-18 12:34:56.789  123  456 I Demo Tag: hello world\n"
 def test_parse_filters_buffer_and_exports(self):
  e=ADBLogcatManager.parse(self.LINE,"S","p");self.assertEqual((e.pid,e.tag),(123,"Demo Tag"));m=ADBLogcatManager(ADB(),lambda a:Process([]),max_lines=1);m.buffer.append(e);m.buffer.append(e);m.dropped=1;self.assertEqual(len(m.filtered(pid=123,tags=("demo tag",),search="world")),1);self.assertIn("hello",m.export_text());self.assertIn('"pid": 123',m.export_jsonl())
 def test_start_stop_pause_clear_and_no_orphan(self):
  process=Process([self.LINE]);seen=[];m=ADBLogcatManager(ADB(),lambda a:process,seen.append);r=m.start("SER","p");m.thread.join();self.assertTrue(r.ok);self.assertEqual(r.preview[1:3],("-s","SER"));m.pause_display(True);self.assertEqual(m.state,LogcatState.PAUSED);m.stop();self.assertTrue(process.terminated);self.assertEqual(m.state,LogcatState.STOPPED)
 def test_clear_device_confirmation(self):
  adb=ADB();m=ADBLogcatManager(adb,lambda a:Process([]));m.serial="S";self.assertFalse(m.clear_device().ok);self.assertTrue(m.clear_device(True).ok);self.assertEqual(adb.calls[-1][1],"S")

if __name__=="__main__":unittest.main()
