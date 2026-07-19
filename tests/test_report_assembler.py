import unittest
from pathlib import Path
from app.core.assessment_scope import AssessmentScope
from app.core.pentest_session import PentestSession
from app.core.report_models import ReportProfile
from app.core.report_assembler import ReportAssembler
from app.core.security_finding import SecurityFinding
class T(unittest.TestCase):
 def test_filter_metadata_no_contents(self):
  scope=AssessmentScope("c","Case",device_serial="s",target_name="t",authorization_confirmed=True);session=PentestSession.draft(scope,Path("/tmp/c"));data=ReportAssembler().assemble(session,ReportProfile("p",minimum_finding_severity="high"),(SecurityFinding("low",severity="low",status="open"),SecurityFinding("high",severity="high",status="open")));self.assertEqual([f["title"] for f in data["findings"]],["high"]);self.assertNotIn("contents",data)
