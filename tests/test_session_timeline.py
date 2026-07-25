import tempfile,unittest
from pathlib import Path
from app.core.pentest_event import EventCategory,PentestEvent
from app.core.session_timeline import SessionTimeline
class TimelineTests(unittest.TestCase):
 def test_append_filter_malformed_exports_correction_and_safe_paths(self):
  with tempfile.TemporaryDirectory() as d:
   timeline=SessionTimeline(d);a=PentestEvent(EventCategory.NOTE,"operator","A","needle",severity="low");b=PentestEvent(EventCategory.ERROR,"runtime","B",severity="high");timeline.append(b);timeline.append(a)
   self.assertEqual(len(timeline.filter("needle",category="note",severity="low",source="operator")),1)
   with timeline.path.open("a") as f:f.write("malformed\n")
   self.assertEqual(timeline.rebuild().malformed_records,1);self.assertTrue(timeline.correction(a.event_id,"fix").ok);self.assertTrue(timeline.export_json(Path(d)/"exports/t.json").ok);self.assertTrue(timeline.export_markdown(Path(d)/"exports/t.md").ok);self.assertFalse(timeline.export_json(Path(d).parent/"escape.json").ok)
