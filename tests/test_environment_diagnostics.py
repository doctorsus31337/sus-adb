import tempfile,unittest
from app.core.environment_diagnostics import EnvironmentDiagnostics
class EnvironmentDiagnosticTests(unittest.TestCase):
 def test_injected_diagnostics_never_execute_real_tools(self):
  calls=[]
  def run(argv):calls.append(argv);return "1.2"
  with tempfile.TemporaryDirectory() as d:
   results=EnvironmentDiagnostics(lookup=lambda name:None,version_runner=run,module_finder=lambda name:None).run(d,d)
  self.assertFalse(calls);self.assertTrue(any(r.name=="Platform" for r in results));self.assertTrue(any(r.name=="adb" and not r.available for r in results))
if __name__=="__main__":unittest.main()
