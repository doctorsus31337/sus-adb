import unittest
from app.plugins.contribution_registry import *
class T(unittest.TestCase):
 def test_duplicate_rollback_and_unregister(self):
  r=ContributionRegistry();r.register("a",(Contribution("one","parser","One"),));self.assertRaises(ValueError,r.register,"b",(Contribution("two","parser","Two"),Contribution("one","parser","Bad")));self.assertFalse(r.by_plugin("b"));self.assertEqual(len(r.unregister_plugin("a")),1);self.assertFalse(r.list())
