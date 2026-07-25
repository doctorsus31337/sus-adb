import unittest
from app.core.performance_monitor import PerformanceMonitor
class PerformanceMonitorTests(unittest.TestCase):
 def test_local_snapshot_and_warning(self):
  monitor=PerformanceMonitor(enabled=True,thresholds={"startup":0.0});monitor.record("startup",0.1);snapshot=monitor.snapshot();self.assertEqual(snapshot.durations["startup"],0.1);self.assertTrue(snapshot.warnings)
if __name__=="__main__":unittest.main()
