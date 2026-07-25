import json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.storage_export_service import StorageExportService
from app.core.storage_models import StorageDifference
class ExportTests(unittest.TestCase):
 def test_json_markdown_csv_metadata_safe_no_overwrite(self):
  with TemporaryDirectory() as td:
   root=Path(td);svc=StorageExportService(lambda:root);j=svc.json(root/"a.json","differences",(StorageDifference("x","added"),),"S","pkg");self.assertTrue(j.ok);self.assertEqual(json.loads(Path(j.path).read_text())["metadata"]["device_serial"],"S");self.assertTrue(svc.markdown(root/"a.md","Storage",("x",),"S","pkg").ok);self.assertTrue(svc.csv(root/"a.csv",("x",),((1,),)).ok);self.assertFalse(svc.json(root/"a.json","x",()).ok);self.assertFalse(svc.json(root.parent/"escape.json","x",()).ok)
