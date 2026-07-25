import tempfile,unittest
from pathlib import Path
from app.core.app_metadata import create_metadata
from app.core.crash_report import CrashReporter
class CrashReportTests(unittest.TestCase):
 def test_report_is_local_and_redacted(self):
  with tempfile.TemporaryDirectory() as d:
   reporter=CrashReporter(d,create_metadata(platform_name="TestOS"),lambda:("token=hidden",))
   report,path=reporter.capture(RuntimeError("password=hunter2 /home/alice/case"),("/tmp/Case One",))
   text=Path(path).read_text();self.assertNotIn("hunter2",text);self.assertNotIn("hidden",text);self.assertEqual(report.workspace_names,("Case One",))
if __name__=="__main__":unittest.main()
