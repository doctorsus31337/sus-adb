import tempfile,unittest
from pathlib import Path
from app.core.apk_workspace_service import ApkWorkspaceService
class T(unittest.TestCase):
 def test_safe_original_duplicate(self):
  with tempfile.TemporaryDirectory() as d:
   s=ApkWorkspaceService(Path(d)/"lab");p=Path(d)/"a.apk";p.write_bytes(b"x");a=s.import_file(p);self.assertTrue(s.safe(a.workspace_relative_path).is_file());self.assertRaises(ValueError,s.import_file,p);self.assertRaises(ValueError,s.safe,"../x")
