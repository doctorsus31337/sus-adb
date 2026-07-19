import tempfile,unittest,zipfile
from pathlib import Path
from app.core.apk_acquisition_service import ApkAcquisitionService
class T(unittest.TestCase):
 def test_archive_safety(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"x.zip";
   with zipfile.ZipFile(p,"w") as z:z.writestr("../x","x")
   self.assertRaises(ValueError,ApkAcquisitionService(None,None,None).inspect_container,p)
