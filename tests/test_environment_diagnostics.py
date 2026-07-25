import tempfile,unittest
from types import SimpleNamespace
from app.core.environment_diagnostics import EnvironmentDiagnostics
from app.core.host_tool_resolver import HostToolResolver
class EnvironmentDiagnosticTests(unittest.TestCase):
 def test_injected_diagnostics_never_execute_real_tools(self):
  calls=[]
  def run(argv):calls.append(argv);return "1.2"
  with tempfile.TemporaryDirectory() as d:
   resolver=HostToolResolver(which=lambda name:None,packaged=True)
   results=EnvironmentDiagnostics(resolver=resolver,version_runner=run,module_finder=lambda name:None).run(d,d)
  self.assertFalse(calls);self.assertTrue(any(r.name=="Platform" for r in results));self.assertTrue(any(r.name=="adb" and not r.available for r in results))
 def test_missing_paths_are_not_created(self):
  with tempfile.TemporaryDirectory() as d:
   missing=__import__('pathlib').Path(d)/"not-created";EnvironmentDiagnostics(lookup=lambda name:None,module_finder=lambda name:None).run(missing,missing);self.assertFalse(missing.exists())
 def test_python_frida_is_independent_of_missing_external_clis(self):
  module=SimpleNamespace(__version__="17.15.5")
  records=EnvironmentDiagnostics(lookup=lambda name:None,module_finder=lambda name:object(),frida_provider=lambda:module).run()
  by_name={record.name:record for record in records}
  self.assertTrue(by_name["Frida Python"].available);self.assertEqual(by_name["Frida Python"].version,"17.15.5")
  self.assertFalse(by_name["frida"].available);self.assertFalse(by_name["frida-ps"].available);self.assertFalse(by_name["objection"].available)
 def test_source_and_frozen_module_discovery(self):
  for packaged in (False,True):
   with self.subTest(packaged=packaged):
    resolver=HostToolResolver(which=lambda name:None,packaged=packaged)
    records=EnvironmentDiagnostics(resolver=resolver,module_finder=lambda name:object(),frida_provider=lambda:SimpleNamespace(__version__="17.15.5")).run()
    self.assertTrue(next(record for record in records if record.name=="Frida Python").available)
if __name__=="__main__":unittest.main()
