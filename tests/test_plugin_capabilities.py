import unittest
from app.plugins.plugin_capabilities import *
class Scope:
 def permits(self,c):return False
class T(unittest.TestCase):
 def test_default_deny_and_scope_override(self):
  self.assertFalse(CapabilityPolicy().check("read-selected-device").allowed);self.assertTrue(CapabilityPolicy(("read-selected-device",)).check("read-selected-device").allowed);self.assertFalse(CapabilityPolicy(("modify-device-state",)).check("modify-device-state",Scope()).allowed)
