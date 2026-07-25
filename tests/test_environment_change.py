import unittest
from app.core.environment_change import ChangeState,EnvironmentChange
class EnvironmentChangeTests(unittest.TestCase):
 def test_roundtrip_defaults(self):
  change=EnvironmentChange("forwarding","Port",restoration_instructions="remove",restoration_command_preview="adb forward --remove",destructive=True);self.assertEqual(change.state,ChangeState.PLANNED);self.assertEqual(EnvironmentChange.from_dict(change.to_dict()),change)
