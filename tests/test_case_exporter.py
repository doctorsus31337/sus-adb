import json,tempfile,unittest
from datetime import date
from pathlib import Path
from app.core.assessment_scope import AssessmentScope
from app.core.case_exporter import CaseExporter
from app.core.environment_change import EnvironmentChange
from app.core.evidence_item import EvidenceItem,EvidenceType
from app.core.pentest_session import PentestSession
class CaseExporterTests(unittest.TestCase):
 def test_deterministic_json_markdown_metadata_and_safe_path(self):
  with tempfile.TemporaryDirectory() as d:
   scope=AssessmentScope("s","Case",authorization_confirmed=True,device_serial="d",package_identifier="p",allowed_actions=("recon",),excluded_actions=("destructive-testing",),start_date=date.today().isoformat());session=PentestSession.draft(scope,d).update_tools({"frida":"1"});evidence=EvidenceItem(EvidenceType.FILE,"E","evidence/x","a"*64,99);change=EnvironmentChange("proxy","Proxy",restoration_instructions="restore");exporter=CaseExporter(d);result=exporter.export_json(session,evidence=(evidence,),changes=(change,));data=json.loads(Path(result.path).read_text());self.assertEqual(data["evidence_manifest"][0]["sha256"],"a"*64);self.assertNotIn("contents",data["evidence_manifest"][0]);self.assertTrue(exporter.export_markdown(session,evidence=(evidence,),changes=(change,)).ok);self.assertTrue(exporter.unresolved_checklist((change,)).ok);self.assertFalse(exporter._write("../escape","x").ok)
