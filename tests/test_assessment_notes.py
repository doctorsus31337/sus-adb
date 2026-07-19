import tempfile,unittest
from pathlib import Path
from app.core.assessment_notes import AssessmentNotes
class AssessmentNotesTests(unittest.TestCase):
 def test_create_edit_search_delete_export_safe_paths(self):
  with tempfile.TemporaryDirectory() as d:
   notes=AssessmentNotes(d);created=notes.create("Title","Body",tags=("tag",),related_evidence_ids=("e",));self.assertTrue(created.ok);edited=notes.edit(created.note.note_id,body="Changed");self.assertEqual(edited.note.body,"Changed");self.assertEqual(len(notes.search("changed",tag="tag")),1);self.assertTrue(notes.export_markdown(Path(d)/"exports/notes.md").ok);self.assertFalse(notes.export_markdown(Path(d).parent/"escape.md").ok);self.assertFalse(notes.delete(created.note.note_id).ok);self.assertTrue(notes.delete(created.note.note_id,confirmed=True).ok)
