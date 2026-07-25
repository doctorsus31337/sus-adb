import tempfile,unittest
from pathlib import Path
from app.core.assessment_scope import AssessmentScope
from app.core.pentest_session import PentestSession
from app.core.report_models import ReportProfile
from app.core.report_export_service import ReportExportService
class T(unittest.TestCase):
 def test_exports_hash_history_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   s=PentestSession.draft(AssessmentScope("c","Case",device_serial="s",target_name="t"),d);p=ReportProfile("p");data={"cover":{"title":"R","subtitle":"","classification":"I"},"executive_summary":{"finding_count":0},"findings":[],"evidence_manifest":[],"timeline":[],"unresolved_environment_changes":[],"limitations":[]};x=ReportExportService(d);r=x.export(s,p,data,("json",));self.assertTrue(r.ok);self.assertEqual(len(r.hashes),1);self.assertFalse(x.export(s,p,data,("json",)).ok);self.assertEqual(len(x.history()),1)
