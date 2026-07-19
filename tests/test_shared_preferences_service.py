import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.shared_preferences_service import SharedPreferencesService
class Session:
 def permits(self,c):return True
class PreferencesTests(unittest.TestCase):
 def test_types_search_reveal_exports_and_compare(self):
  xml='<map><string name="s">long value</string><int name="i" value="2"/><long name="l" value="3"/><float name="f" value="1.5"/><boolean name="b" value="true"/><set name="set"><string>x</string></set><null name="n"/></map>'
  with TemporaryDirectory() as td:
   p=Path(td)/"prefs.xml";p.write_text(xml);svc=SharedPreferencesService(4);r=svc.parse(p,"S","pkg",("s",));self.assertTrue(r.ok);self.assertEqual(len(r.entries),7);self.assertTrue(svc.search("i"));self.assertTrue(svc.reveal(r.entries[0],Session()).ok);self.assertTrue(svc.export_json(Path(td)/"out.json").ok);self.assertTrue(svc.export_markdown(Path(td)/"out.md").ok);self.assertTrue(svc.compare(r.entries,()))
 def test_malformed_and_entities_rejected(self):
  with TemporaryDirectory() as td:
   p=Path(td)/"x";p.write_text('<!DOCTYPE x [<!ENTITY a "x">]><map/>');self.assertFalse(SharedPreferencesService().parse(p).ok);p.write_text("<map>");self.assertFalse(SharedPreferencesService().parse(p).ok)
