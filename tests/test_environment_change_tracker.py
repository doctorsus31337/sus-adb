import tempfile,unittest
from datetime import date
from app.core.assessment_scope import AssessmentScope
from app.core.environment_change import ChangeState,EnvironmentChange
from app.core.environment_change_tracker import EnvironmentChangeTracker
from app.core.session_timeline import SessionTimeline
class ChangeTrackerTests(unittest.TestCase):
 def test_states_scope_confirmation_timeline_guidance_no_execution(self):
  with tempfile.TemporaryDirectory() as d:
   timeline=SessionTimeline(d);tracker=EnvironmentChangeTracker(d,timeline);change=EnvironmentChange("proxy","Proxy",reversible=False,destructive=True,restoration_instructions="restore",restoration_command_preview="adb shell settings put")
   tracker.register(change);scope=AssessmentScope("s","c",authorization_confirmed=True,device_serial="d",package_identifier="p",allowed_actions=("destructive-testing",),start_date=date.today().isoformat());self.assertFalse(tracker.mark_applied(change.change_id,scope,confirmed=True).ok);self.assertFalse(tracker.mark_applied(change.change_id,scope,session_active=True).ok);applied=tracker.mark_applied(change.change_id,scope,confirmed=True,session_active=True);self.assertEqual(applied.change.state,ChangeState.APPLIED);self.assertIn("guidance only",tracker.restoration_guidance(applied.change));failed=tracker.mark_restoration_failed(change.change_id,"failed");self.assertIn(failed.change,tracker.unresolved());self.assertEqual(tracker.mark_restored(change.change_id).change.state,ChangeState.RESTORED);self.assertGreaterEqual(len(timeline.events()),4)
