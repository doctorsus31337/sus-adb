import importlib.util,unittest
import tempfile
from pathlib import Path
class ReleaseAuditTests(unittest.TestCase):
 def test_patterns_detect_without_exposing_secret(self):
  path=Path(__file__).parents[1]/"scripts/audit_release.py";spec=importlib.util.spec_from_file_location("audit_release",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  fake=b"token=not-a-real-secret ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  matches=[name for name,pattern in module.PATTERNS if pattern.search(fake)]
  self.assertIn("token",matches);self.assertNotIn("not-a-real-secret",repr(matches))
 def test_tree_audit_reports_path_not_secret(self):
  path=Path(__file__).parents[1]/"scripts/audit_release.py";spec=importlib.util.spec_from_file_location("audit_release",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:
   suspect=Path(d)/"capture.pcap";suspect.write_bytes(b"private-content");findings=module.audit_tree(d);self.assertEqual(findings,(("capture.pcap","generated-artifact"),));self.assertNotIn("private-content",repr(findings))
if __name__=="__main__":unittest.main()
