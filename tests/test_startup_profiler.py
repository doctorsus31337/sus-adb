import threading
import unittest

from app.core.startup_profiler import StartupProfiler


class FakeClock:
    def __init__(self):self.value=10.0
    def __call__(self):return self.value
    def advance(self,value):self.value+=value


class StartupProfilerTests(unittest.TestCase):
    def test_monotonic_stage_order_and_duration_with_fake_clock(self):
        clock=FakeClock();profiler=StartupProfiler(clock=clock,origin=10,max_stages=4)
        with profiler.stage("configuration"):
            clock.advance(.25)
        clock.advance(.1)
        with profiler.stage("shell"):
            clock.advance(.5)
        first,second=profiler.stages();self.assertEqual(first.name,"configuration");self.assertAlmostEqual(first.duration,.25);self.assertAlmostEqual(second.start_offset,.35);self.assertAlmostEqual(second.duration,.5)

    def test_failure_bounded_history_and_sanitized_report(self):
        clock=FakeClock();profiler=StartupProfiler(clock=clock,max_stages=2)
        with self.assertRaisesRegex(RuntimeError,"boom"):
            with profiler.stage("broken",note="/"+"home"+"/"+"developer"+"/project"):
                clock.advance(.1);raise RuntimeError("boom")
        profiler.record("next",note="C:"+"\\"+"Users"+"\\Developer\\project")
        profiler.record("last")
        self.assertEqual(tuple(stage.name for stage in profiler.stages()),("next","last"));report=profiler.summary();self.assertNotIn("developer",report.casefold());self.assertNotIn("C:\\Users",report);self.assertIn("No telemetry",report)

    def test_thread_classification_is_local_and_deterministic(self):
        profiler=StartupProfiler();seen=[]
        worker=threading.Thread(target=lambda:seen.append(profiler.record("worker",classification="deferred")))
        worker.start();worker.join();self.assertEqual(seen[0].thread,"worker");self.assertEqual(seen[0].classification,"deferred")


if __name__=="__main__":unittest.main()
