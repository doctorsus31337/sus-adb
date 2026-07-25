import tempfile
import unittest
from pathlib import Path

from app.core.script_descriptor import TrustState
from app.core.script_library import ScriptLibrary


class ScriptLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name) / "scripts"; self.library = ScriptLibrary(self.root)
    def tearDown(self): self.temp.cleanup()

    def test_create_save_load_search_rename_delete_and_digest(self):
        created = self.library.create("agent", "send('ok');")
        self.assertTrue(created.ok); self.assertEqual(len(created.descriptor.sha256), 64)
        self.assertEqual(self.library.load_source(created.descriptor).text, "send('ok');")
        saved = self.library.save_source(created.descriptor, "send('new');"); self.assertNotEqual(saved.descriptor.sha256, created.descriptor.sha256)
        self.assertEqual(self.library.scan().descriptors[0].name, "agent")
        self.assertEqual(self.library.search("agent", trust="trusted-local")[0].name, "agent")
        renamed = self.library.rename(saved.descriptor, "renamed"); self.assertTrue(renamed.ok)
        self.assertFalse(self.library.delete(renamed.descriptor).ok)
        self.assertTrue(self.library.delete(renamed.descriptor, confirmed=True).ok)

    def test_import_is_untrusted_duplicate_safe_and_never_executes(self):
        source = Path(self.temp.name) / "outside.js"; source.write_text("send('x')", encoding="utf-8")
        imported = self.library.import_file(source); self.assertTrue(imported.ok); self.assertEqual(imported.descriptor.trust, TrustState.UNTRUSTED)
        self.assertFalse(self.library.import_file(source).ok)

    def test_safe_path_and_typescript_storage(self):
        with self.assertRaises(ValueError): self.library._safe(self.root / ".." / "escape.js")
        self.assertTrue(self.library.create("editable", "let x: number", suffix=".ts").ok)
