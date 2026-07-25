import unittest
from app.core.redaction_service import *
class T(unittest.TestCase):
 def test_preview_preserves_source(self):
  source="serial ABC secret=x";r=RedactionService((RedactionRule("device-serial","ABC"),RedactionRule("regex",r"secret=\w+"))).preview(source);self.assertEqual(source,"serial ABC secret=x");self.assertNotIn("ABC",r.redacted);self.assertEqual(len(r.substitutions),2);self.assertTrue(RedactionService.likely_sensitive("password=x"))
