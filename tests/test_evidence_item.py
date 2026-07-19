import unittest
from app.core.evidence_item import EvidenceItem,EvidenceType,Sensitivity
class EvidenceItemTests(unittest.TestCase):
 def test_roundtrip_metadata(self):
  item=EvidenceItem(EvidenceType.LOG,"Log","evidence/x","0"*64,4,sensitivity=Sensitivity.RESTRICTED,related_event_ids=("e",),derived_from_id="parent");self.assertEqual(EvidenceItem.from_dict(item.to_dict()),item)
