import tempfile,unittest,zipfile
from pathlib import Path
from app.core.apk_inspection_service import ApkInspectionService
class T(unittest.TestCase):
 def test_no_execution_inventory(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"a.apk";
   with zipfile.ZipFile(p,"w") as z:z.writestr("lib/arm64-v8a/libx.so",b"x")
   r=ApkInspectionService().inspect(p,"p");self.assertEqual(r["summary"].architectures,("arm64-v8a",));self.assertTrue(r["warnings"])
