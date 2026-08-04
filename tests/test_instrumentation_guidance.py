import unittest

from app.core.context_help import HelpRegistry
from app.core.guide_engine import GuideEngine, GuideGoal, GuideState
from app.gui.context_help_window import ContextHelpWindow
from app.gui.guided_setup_window import GuidedSetupWindow


class InstrumentationGuidanceTests(unittest.TestCase):
    def test_every_guided_setup_step_has_unique_specific_body(self):
        state = GuideState(
            selected_serial="SERIAL", adb_state="device",
            host_frida_available=True, frida_endpoint_reachable=True,
            installed_apps_scanned=True, selected_package="org.example.app",
        )
        plan = GuideEngine().plan(GuideGoal.OBSERVE_RUNNING, state)
        bodies = tuple(
            GuidedSetupWindow.step_body(index, plan, state)
            for index in range(len(GuidedSetupWindow.STEPS))
        )
        self.assertEqual(len(bodies), len(set(bodies)))
        selectors = bodies[6]
        for option in ("-p", "-N", "-F", "-f"):
            self.assertIn(option, selectors)
        self.assertIn("-i", bodies[7])
        self.assertIn("-j", bodies[7])
        self.assertNotIn(plan.summary, bodies[0])

    def test_instrumentation_help_topics_render_their_own_bodies(self):
        registry = HelpRegistry()
        topic_ids = (
            "instrumentation-overview", "targets", "sessions",
            "frida-assistant", "objection-assistant",
        )
        bodies = {
            topic_id: ContextHelpWindow.format_topic(registry.get(topic_id))
            for topic_id in topic_ids
        }
        self.assertEqual(len(bodies), len(set(bodies.values())))
        self.assertIn("serial changes during a scan", bodies["targets"].casefold())
        self.assertIn("-N", bodies["frida-assistant"])
        self.assertIn("broken Objection executable", bodies["sessions"])
        self.assertIn("health", bodies["instrumentation-overview"].casefold())


if __name__ == "__main__":
    unittest.main()
