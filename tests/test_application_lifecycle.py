import time,unittest
from app.core.application_lifecycle import ApplicationLifecycle
class LifecycleTests(unittest.TestCase):
 def test_order_and_reverse_cleanup(self):
  calls=[];life=ApplicationLifecycle();result=life.startup({"gui":lambda:calls.append("gui"),"metadata":lambda:calls.append("metadata")});self.assertTrue(result.ok);self.assertEqual(calls,["metadata","gui"])
  life.add_cleanup("first",lambda:calls.append("first"));life.add_cleanup("second",lambda:calls.append("second"));self.assertTrue(life.shutdown().ok);self.assertEqual(calls[-2:],["second","first"])
 def test_blocking_cleanup_is_bounded(self):
  life=ApplicationLifecycle(shutdown_timeout=.03);life.add_cleanup("blocked",lambda:time.sleep(1));started=time.monotonic();result=life.shutdown();self.assertLess(time.monotonic()-started,.2);self.assertFalse(result.ok);self.assertIn("timed out",result.errors[0])
if __name__=="__main__":unittest.main()
