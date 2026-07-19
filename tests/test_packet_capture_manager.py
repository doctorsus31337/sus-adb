import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from app.core.command_result import CommandResult
from app.core.network_models import PacketCaptureConfig,CaptureState
from app.core.packet_capture_manager import PacketCaptureManager

class ADB:
 def __init__(self,data=b"pcap"):self.calls=[];self.data=data
 def run(self,*a,serial=None,timeout=0):
  self.calls.append((a,serial))
  if a and a[0]=="pull":Path(a[2]).write_bytes(self.data)
  return CommandResult.from_command(a,0,"/system/bin/tcpdump")
class Process:
 def start(self,a):return SimpleNamespace(running=True,error=None)
 def stop(self):return SimpleNamespace(error=None)
 def cancel(self):return SimpleNamespace(error=None)
class Session:
 scope=SimpleNamespace(device_serial="SER")
 def permits(self,c):return True
class CaptureManagerTests(unittest.TestCase):
 def test_bounded_capture_pull_hash_cleanup(self):
  with TemporaryDirectory() as td:
   adb=ADB();clock=iter((1.0,3.0,3.0));m=PacketCaptureManager(adb,Process(),lambda:Session(),clock=lambda:next(clock));cfg=PacketCaptureConfig("SER",duration=30,local_destination=str(Path(td)/"a.pcap"));self.assertTrue(m.start(cfg,True).ok);r=m.stop();self.assertTrue(r.ok);self.assertEqual(r.value.capture_state,CaptureState.COMPLETED);self.assertEqual(len(r.value.sha256),64);self.assertTrue(any("rm" in a[0] for a in adb.calls))
 def test_limits_no_overwrite_import_disconnect(self):
  with TemporaryDirectory() as td:
   p=Path(td)/"x.pcap";p.write_bytes(b"x");m=PacketCaptureManager(ADB(),Process(),lambda:Session());self.assertFalse(m.start(PacketCaptureConfig("SER",duration=301),True).ok);self.assertFalse(m.start(PacketCaptureConfig("SER",local_destination=str(p)),True).ok);self.assertEqual(len(m.import_pcap(p).value.sha256),64)
