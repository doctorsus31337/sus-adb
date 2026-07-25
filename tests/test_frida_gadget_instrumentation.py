import tempfile,unittest
from pathlib import Path
from app.core.frida_gadget_instrumentation import FridaGadgetInstrumentation
class S:
 def permits(self,c):return True
class T(unittest.TestCase):
 def test_explicit_arch_scope_plan(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"g.so";p.write_bytes(b"g");r=FridaGadgetInstrumentation().plan(None,("arm64-v8a",),p,"arm64-v8a",{"interaction":{"type":"listen"}},S());self.assertTrue(r[0]);self.assertEqual(len(r[1]["sha256"]),64);self.assertFalse(FridaGadgetInstrumentation().apply(r[1],Path(d)/"out",False)[0])
