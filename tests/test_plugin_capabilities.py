import unittest
from app.plugins.plugin_capabilities import *
class Scope:
 def permits(self,c):return False
class T(unittest.TestCase):
 def test_default_deny_and_scope_override(self):
  self.assertFalse(CapabilityPolicy().check("read-selected-device").allowed);self.assertTrue(CapabilityPolicy(("read-selected-device",)).check("read-selected-device").allowed);self.assertFalse(CapabilityPolicy(("modify-device-state",)).check("modify-device-state",Scope()).allowed)
 def test_device_logs_are_known_explicit_and_privacy_sensitive(self):
  self.assertIn("read-device-logs",CAPABILITIES);self.assertFalse(CapabilityPolicy().check("read-device-logs").allowed);result=CapabilityPolicy(("read-device-logs",)).check("read-device-logs");self.assertTrue(result.allowed);self.assertIn("tokens",result.caution)
