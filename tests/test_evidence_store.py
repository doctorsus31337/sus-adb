import tempfile,unittest
from pathlib import Path
from app.core.evidence_item import Sensitivity
from app.core.evidence_store import EvidenceStore
class EvidenceStoreTests(unittest.TestCase):
 def test_import_hash_duplicate_text_search_retrieve_delete_manifest_and_safety(self):
  with tempfile.TemporaryDirectory() as d:
   store=EvidenceStore(d,"case");source=Path(d)/"input.bin";source.write_bytes(b"abc");added=store.import_file(source,"File",sensitivity=Sensitivity.CONFIDENTIAL,tags=("tag",));self.assertTrue(added.ok);self.assertEqual(len(added.item.sha256),64);self.assertFalse(store.import_file(source).ok);text=store.add_command_output("Output","hello");self.assertTrue(text.ok);self.assertEqual(len(store.search("File",sensitivity="confidential",tag="tag")),1);self.assertTrue(store.retrieve(added.item).ok);self.assertFalse(store.delete(added.item).ok);self.assertTrue(store.export_manifest(store.root/"exports/m.json",selected_ids=(added.item.evidence_id,)).ok);self.assertFalse(store.export_manifest(Path(d)/"escape.json").ok);self.assertTrue(store.delete(added.item,confirmed=True).ok)
