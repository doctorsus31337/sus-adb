import tempfile,unittest
from app.core.recovery_manager import RecoveryManager
class RecoveryManagerTests(unittest.TestCase):
 def test_unclean_marker_and_clean_shutdown(self):
  with tempfile.TemporaryDirectory() as d:
   r=RecoveryManager(d);self.assertFalse(r.begin_startup());self.assertTrue(r.begin_startup());self.assertTrue(r.mark_clean_shutdown());self.assertFalse(r.marker.exists())
if __name__=="__main__":unittest.main()
