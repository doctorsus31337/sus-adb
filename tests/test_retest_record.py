import unittest
from app.core.retest_record import RetestRecord
class T(unittest.TestCase):
 def test_roundtrip(self):
  r=RetestRecord("f","2","s","tester","fixed",evidence_ids=("e",));self.assertEqual(RetestRecord.from_dict(r.to_dict()),r);self.assertIn("fixed",r.display_label)
