import unittest,json
from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.storage_snapshot_service import StorageSnapshotService
class SnapshotTests(unittest.TestCase):
 def test_selected_bounded_hash_manifest_compare(self):
  with TemporaryDirectory() as td:
   root=Path(td);src=root/"src";src.mkdir();(src/"a").write_text("one");svc=StorageSnapshotService(max_files=10,max_total_size=100);a=svc.create((src,),root/"one");self.assertTrue(a.ok);self.assertEqual(a.value.file_count,1);(src/"a").write_text("two");(src/"b").write_text("b");b=svc.create((src,),root/"two");diff=svc.compare(a.value,b.value);self.assertEqual({x.status.value for x in diff.value},{"modified","added"});self.assertEqual(json.loads(Path(a.value.manifest_path).read_text())[0]["path"],"src/a")
 def test_limits_empty_symlink_and_cancel(self):
  with TemporaryDirectory() as td:
   root=Path(td);src=root/"s";src.mkdir();(src/"a").write_text("long");svc=StorageSnapshotService(max_total_size=1);self.assertFalse(svc.create((src,),root/"d").ok);self.assertFalse(svc.create((),root/"x").ok);svc.cancel();self.assertTrue(svc.cancelled)
