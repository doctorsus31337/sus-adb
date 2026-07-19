import tempfile,unittest
from app.core.environment_diagnostics import EnvironmentDiagnostics
class EnvironmentDiagnosticTests(unittest.TestCase):
 def test_injected_diagnostics_never_execute_real_tools(self):
  calls=[]
  def run(argv):calls.append(argv);return "1.2"
  with tempfile.TemporaryDirectory() as d:
   results=EnvironmentDiagnostics(lookup=lambda name:None,version_runner=run,module_finder=lambda name:None).run(d,d)
  self.assertFalse(calls);self.assertTrue(any(r.name=="Platform" for r in results));self.assertTrue(any(r.name=="adb" and not r.available for r in results))
 def test_missing_paths_are_not_created(self):
  with tempfile.TemporaryDirectory() as d:
   missing=__import__('pathlib').Path(d)/"not-created";EnvironmentDiagnostics(lookup=lambda name:None,module_finder=lambda name:None).run(missing,missing);self.assertFalse(missing.exists())
if __name__=="__main__":unittest.main()
