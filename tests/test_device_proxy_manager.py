import unittest
from types import SimpleNamespace
from app.core.command_result import CommandResult
from app.core.device_proxy_manager import DeviceProxyManager

class ADB:
 def __init__(self):self.calls=[]
 def run(self,*args,serial=None,timeout=0):self.calls.append((args,serial));out="old:8080" if args[:5]==("shell","settings","get","global","http_proxy") else "";return CommandResult.from_command(args,0,out)
class Session:
 scope=SimpleNamespace(device_serial="SER",package_identifier="pkg")
 def __init__(self,permit=True):self.permit=permit
 def permits(self,c):return self.permit
class Sink:
 def __init__(self):self.items=[]
 def append(self,x):self.items.append(x)
 def register(self,x):self.items.append(x)
class DeviceProxyTests(unittest.TestCase):
 def test_capture_original_apply_restore_and_serial(self):
  adb=ADB();timeline=Sink();changes=Sink();m=DeviceProxyManager(adb,lambda:Session(),lambda:timeline,lambda:changes);m.select("SER")
  self.assertTrue(m.inspect().ok);self.assertTrue(m.apply_proxy("10.0.2.2",8080,True).ok);self.assertEqual(m.state.original_proxy_value,"old:8080");self.assertTrue(m.restore_proxy(True).ok);self.assertTrue(all(s=="SER" for _,s in adb.calls));self.assertTrue(timeline.items);self.assertTrue(changes.items)
 def test_scope_confirmation_invalid_port_and_owned_mapping(self):
  m=DeviceProxyManager(ADB(),lambda:Session(False));m.select("SER");self.assertFalse(m.apply_proxy("x",8080,True).ok)
  m.session_provider=lambda:Session();self.assertFalse(m.apply_proxy("x",70000,True).ok);self.assertFalse(m.add_mapping("reverse","tcp:1","tcp:2",False).ok)
  added=m.add_mapping("reverse","tcp:1","tcp:2",True);self.assertTrue(added.ok);self.assertFalse(m.remove_mapping(object(),True).ok);self.assertTrue(m.remove_mapping(added.value,True).ok)
