import unittest

from app.core.guide_engine import (
    GuideEngine,
    GuideGoal,
    GuideState,
    InstrumentationRoute,
)


class GuideEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = GuideEngine()

    def test_every_goal_is_deterministic_and_never_executes(self):
        state = GuideState(selected_serial="SERIAL", adb_state="device")
        for goal in GuideGoal:
            first = self.engine.plan(goal, state)
            self.assertEqual(first, self.engine.plan(goal.value, state))
            self.assertFalse(first.executes_automatically)
            self.assertTrue(first.actions or first.blockers)

    def test_installed_app_route_needs_adb_but_not_frida(self):
        state = GuideState(selected_serial="SERIAL", adb_state="device")
        plan = self.engine.plan(GuideGoal.SEE_INSTALLED_APPS, state)
        self.assertEqual(plan.route, InstrumentationRoute.ADB_ONLY)
        self.assertEqual(plan.actions[-1].destination, "targets-installed")
        self.assertIn("Frida is not required", plan.actions[-1].explanation)

    def test_routes_are_structured_and_connection_failures_are_blocked(self):
        rooted = GuideState(
            selected_serial="SERIAL", adb_state="device",
            root_available=True, server_available=True,
            frida_endpoint_reachable=True,
        )
        self.assertEqual(
            self.engine.determine_route(rooted),
            InstrumentationRoute.ROOTED_SERVER_READY,
        )
        offline = GuideState(selected_serial="SERIAL", adb_state="offline")
        plan = self.engine.plan(GuideGoal.OPEN_ADB_SHELL, offline)
        self.assertEqual(plan.route, InstrumentationRoute.BLOCKED)
        self.assertIn("offline", plan.blockers[0])

    def test_recovery_warning_and_no_automatic_device_action(self):
        plan = self.engine.plan(
            GuideGoal.RECOVER_FILES,
            GuideState(selected_serial="SERIAL", adb_state="device"),
        )
        self.assertIn("commonly wipes user data", plan.warnings[0])
        self.assertFalse(plan.executes_automatically)


if __name__ == "__main__":
    unittest.main()
