import tempfile,unittest
from pathlib import Path
from app.core.logging_manager import LoggingManager
class LoggingManagerTests(unittest.TestCase):
 def test_secret_and_home_are_redacted(self):
  with tempfile.TemporaryDirectory() as d:
   m=LoggingManager(d);m.log("INFO","password=hunter2 /home/alice/case");m.close();text=next(Path(d).glob("application.*")).read_text();self.assertNotIn("hunter2",text);self.assertNotIn("/home/alice",text)
if __name__=="__main__":unittest.main()
