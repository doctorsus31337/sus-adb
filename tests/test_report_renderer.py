import json,unittest
from app.core.report_renderer import ReportRenderer
class T(unittest.TestCase):
 def data(self):return {"cover":{"title":"<script>alert(1)</script>","subtitle":"","classification":"Internal"},"executive_summary":{"finding_count":1},"findings":[{"finding_id":"1","severity":"high","title":"<img onerror=x>","detailed_description":"<script>x</script>","impact":"i","remediation":"r"}],"evidence_manifest":[{"title":"e","sha256":"abc"}],"unresolved_environment_changes":[],"limitations":[]}
 def test_safe_offline_deterministic(self):
  h=ReportRenderer.html(self.data());self.assertNotIn("<script>",h);self.assertNotIn("http://",h);self.assertEqual(ReportRenderer.json(self.data()),ReportRenderer.json(self.data()));self.assertIn("Evidence Integrity",ReportRenderer.markdown(self.data()))
