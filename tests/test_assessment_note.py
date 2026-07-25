import unittest
from app.core.assessment_note import AssessmentNote
class AssessmentNoteTests(unittest.TestCase):
 def test_roundtrip_relationships(self):
  note=AssessmentNote("Title","Body",tags=("a",),related_evidence_ids=("e",),related_event_ids=("v",));self.assertEqual(AssessmentNote.from_dict(note.to_dict()),note)
