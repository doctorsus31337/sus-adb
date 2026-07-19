import tempfile,unittest
from app.core.finding_repository import FindingRepository
from app.core.security_finding import SecurityFinding
from app.core.retest_record import RetestRecord
from app.core.retest_service import RetestService
class T(unittest.TestCase):
 def test_transition_history(self):
  with tempfile.TemporaryDirectory() as d:
   repo=FindingRepository(d);f=SecurityFinding("f",detailed_description="d",status="remediated");repo.create(f);result=RetestService(repo).create(RetestRecord(f.finding_id,"2","s","t","fixed"));self.assertTrue(result.ok);self.assertEqual(result.finding.status.value,"closed");self.assertGreaterEqual(len(repo.history(f.finding_id)),2)
