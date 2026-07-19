import tempfile,unittest
from pathlib import Path
from app.core.finding_repository import FindingRepository
from app.core.security_finding import SecurityFinding
class T(unittest.TestCase):
 def test_crud_history_duplicates_safe(self):
  with tempfile.TemporaryDirectory() as d:
   r=FindingRepository(d);f=SecurityFinding("One",detailed_description="d",component_location="/a");self.assertTrue(r.create(f).ok);self.assertTrue(r.duplicate(f.finding_id).ok);self.assertGreaterEqual(len(r.history()),2);self.assertFalse(r.delete(f.finding_id).ok);self.assertTrue(r.delete(f.finding_id,True).ok);self.assertFalse(r.export_json(Path(d).parent/"escape.json").ok)
