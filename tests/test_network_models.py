import unittest
from dataclasses import FrozenInstanceError
from app.core.network_models import *

class NetworkModelTests(unittest.TestCase):
 def test_models_serialize_and_label(self):
  self.assertIn("Burp",HostProxyTool("Burp",installed=True).display_label)
  self.assertEqual(DeviceProxyState("SER",ProxyMode.GLOBAL_HTTP,active_proxy_value="h:1").to_dict()["proxy_mode"],"global-http")
  self.assertIn("tcp:1",PortMapping("SER","reverse","tcp:1","tcp:2").display_label)
  self.assertEqual(PacketCaptureArtifact("SER",capture_state="completed").to_dict()["capture_state"],"completed")
  event=NetworkEvent("request",host="example.test",port=443,url="https://example.test/a",headers={"X":"y"})
  self.assertEqual(event.to_dict()["event_type"],"request");self.assertIn("example.test",event.display_text)
  with self.assertRaises(FrozenInstanceError):event.host="changed"
