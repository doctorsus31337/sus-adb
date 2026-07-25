import unittest
from app.core.packet_capture_process import PacketCaptureProcess

class Proc:
 def __init__(self,*a,**kw):self.returncode=None;self.terminated=False
 def poll(self):return self.returncode
 def terminate(self):self.terminated=True;self.returncode=0
 def communicate(self,timeout=None):return ("out","err")
 def kill(self):self.returncode=-9
class CaptureProcessTests(unittest.TestCase):
 def test_explicit_argv_start_stop_no_shell(self):
  calls=[]
  def factory(argv,**kw):calls.append((argv,kw));return Proc()
  p=PacketCaptureProcess(factory);self.assertTrue(p.start(["adb","-s","SER"]).running);self.assertFalse(p.stop().running);self.assertEqual(calls[0][0],("adb","-s","SER"));self.assertFalse(calls[0][1]["shell"])
