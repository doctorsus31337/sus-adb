import unittest
from app.core.apk_tool_diagnostics import ApkToolDiagnostics
from app.core.command_result import CommandResult
class R:
 def run(self,a,timeout=0):return CommandResult(a,0,"v1")
class T(unittest.TestCase):
 def test_fake(self):
  x=ApkToolDiagnostics(R(),lambda n:"/bin/x" if n=="apktool" else None).diagnose();self.assertTrue(next(v for v in x if v.display_name=="apktool").installed)
