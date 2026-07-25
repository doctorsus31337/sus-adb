import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from app.core.command_result import CommandResult
from app.core.network_tool_diagnostics import NetworkToolDiagnostics

class Runner:
 def __init__(self):self.calls=[]
 def run(self,argv,timeout=0):self.calls.append(tuple(argv));return CommandResult.from_command(argv,0,"v1")
class ToolDiagnosticTests(unittest.TestCase):
 def test_injected_lookup_versions_and_explicit_probe(self):
  runner=Runner();probes=[];d=NetworkToolDiagnostics(runner,lambda n:f"/bin/{n}" if n=="mitmproxy" else None,lambda h,p:probes.append((h,p)) or True)
  r=d.diagnose("127.0.0.1",8080);self.assertTrue(r.ok);self.assertEqual(probes,[("127.0.0.1",8080)]);self.assertEqual(runner.calls,[('/bin/mitmproxy','--version')])
 def test_burp_configured_and_invalid_port(self):
  with TemporaryDirectory() as td:
   p=Path(td)/"burp";p.write_text("");r=NetworkToolDiagnostics(Runner(),lambda n:None,burp_path=str(p)).diagnose("host",8080);self.assertTrue(r.tools[-1].installed)
  self.assertFalse(NetworkToolDiagnostics(Runner()).diagnose("",0).ok)
