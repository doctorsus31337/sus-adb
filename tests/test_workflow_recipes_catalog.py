import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from app.core.context_help import HelpRegistry
from app.core.workflow_recipe_catalog import (
    RecipeHostCallbacks,
    build_recipe_catalog,
)
from app.core.workflow_recipes import (
    RecipeProjectedState,
    RecipeRunController,
    RecipeRunStatus,
    StepActionClass,
)


ROOT = Path(__file__).parents[1]


class CallbackFixture:
    def __init__(self):
        self.calls = []

    def callback(self, name):
        return lambda: self.calls.append(name) or object()

    def callbacks(self):
        return RecipeHostCallbacks(
            focus_device_selector=self.callback("device-selector"),
            open_environment_diagnostics=self.callback("diagnostics"),
            open_installed_applications=self.callback("installed-applications"),
            open_readiness_advisor=self.callback("readiness-advisor"),
            open_frida_assistant=self.callback("frida-assistant"),
            open_frida_sessions=self.callback("frida-sessions"),
            open_device_recovery=self.callback("device-recovery"),
            open_pentest=self.callback("pentest"),
            open_assessment_scope=self.callback("assessment-scope"),
            open_findings=self.callback("findings"),
            open_timeline=self.callback("timeline"),
        )


class WorkflowRecipeCatalogTests(unittest.TestCase):
    EXPECTED = {
        "device-readiness",
        "frida-readiness",
        "instrumentation-session",
        "broken-screen-recovery",
        "authorized-assessment-setup",
    }

    def setUp(self):
        self.fixture = CallbackFixture()
        self.catalog = build_recipe_catalog(self.fixture.callbacks())
        self.by_id = {recipe.recipe_id: recipe for recipe in self.catalog}
        self.host = RecipeProjectedState(
            selected_serial="SERIAL-A",
            device_name="Fixture",
            device_state="device",
            selected_target="org.example.fixture",
            target_name="Fixture App",
            assessment_name="Authorized Fixture",
            authorization_confirmed=True,
        )

    def test_catalog_contains_only_the_five_v1_host_recipes(self):
        self.assertEqual(set(self.by_id), self.EXPECTED)
        self.assertEqual(len(self.catalog), 5)
        self.assertTrue(all(recipe.steps for recipe in self.catalog))
        self.assertTrue(
            all(recipe.prerequisites and recipe.aliases for recipe in self.catalog)
        )

    def test_catalog_construction_and_run_start_invoke_nothing(self):
        self.assertFalse(self.fixture.calls)
        for recipe in self.catalog:
            controller = RecipeRunController((recipe,))
            controller.start(recipe.recipe_id, self.host)
            self.assertEqual(controller.state.status, RecipeRunStatus.ACTIVE)
        self.assertFalse(self.fixture.calls)

    def test_callback_contract_is_frozen_narrow_and_manager_free(self):
        callbacks = self.fixture.callbacks()
        with self.assertRaises(FrozenInstanceError):
            callbacks.open_pentest = lambda: None
        names = set(callbacks.__slots__)
        self.assertFalse(
            names & {
                "root",
                "manager",
                "adb",
                "frida",
                "subprocess",
                "filesystem",
                "worker",
            }
        )

    def test_step_classifications_are_visible_and_non_destructive(self):
        classifications = {
            step.classification
            for recipe in self.catalog
            for step in recipe.steps
        }
        self.assertEqual(classifications, set(StepActionClass))
        self.assertNotIn("destructive", {item.value for item in classifications})

    def test_device_readiness_interprets_states_without_device_actions(self):
        recipe = self.by_id["device-readiness"]
        check = next(step for step in recipe.steps if step.step_id == "review-device-state")
        self.assertTrue(check.invoke(self.host).ok)
        offline = check.invoke(
            RecipeProjectedState(
                selected_serial="SERIAL-A", device_state="offline"
            )
        )
        self.assertFalse(offline.ok)
        self.assertIn("offline", offline.summary)
        self.assertFalse(self.fixture.calls)
        source = " ".join(step.title.casefold() for step in recipe.steps)
        self.assertNotIn("reboot device", source)
        self.assertNotIn("authorize device", source)

    def test_frida_recipe_opens_existing_tools_and_never_starts_runtime(self):
        recipe = self.by_id["frida-readiness"]
        open_steps = tuple(step for step in recipe.steps if step.invoke)
        navigation = tuple(
            step for step in open_steps
            if step.classification is StepActionClass.NAVIGATION
        )
        for step in navigation:
            self.assertTrue(step.invoke(self.host).ok)
        self.assertEqual(
            self.fixture.calls,
            ["diagnostics", "readiness-advisor", "frida-assistant"],
        )
        combined = " ".join(
            (recipe.description, *(step.explanation for step in recipe.steps))
        ).casefold()
        for prohibited in ("start frida server", "upload binaries", "attach automatically"):
            self.assertNotIn(prohibited, combined)

    def test_instrumentation_recipe_routes_but_never_launches_session(self):
        recipe = self.by_id["instrumentation-session"]
        sessions = next(
            step for step in recipe.steps
            if step.step_id == "open-frida-sessions"
        )
        self.assertTrue(sessions.invoke(self.host).ok)
        self.assertEqual(self.fixture.calls, ["frida-sessions"])
        self.assertTrue(
            any(step.step_id == "stop-before-session-launch" for step in recipe.steps)
        )
        self.assertFalse(any("launch" in name for name in self.fixture.calls))

    def test_recovery_recipe_opens_rescue_but_never_copies(self):
        recipe = self.by_id["broken-screen-recovery"]
        open_step = next(
            step for step in recipe.steps
            if step.step_id == "open-device-recovery"
        )
        self.assertTrue(open_step.invoke(self.host).ok)
        self.assertEqual(self.fixture.calls, ["device-recovery"])
        callback_fields = " ".join(RecipeHostCallbacks.__slots__).casefold()
        for prohibited in ("copy", "pull", "delete", "flash", "root", "unlock"):
            self.assertNotIn(prohibited, callback_fields)

    def test_assessment_scope_is_the_only_state_changing_step(self):
        changing = tuple(
            (recipe.recipe_id, step)
            for recipe in self.catalog
            for step in recipe.steps
            if step.classification is StepActionClass.STATE_CHANGING
        )
        self.assertEqual(len(changing), 1)
        recipe_id, scope = changing[0]
        self.assertEqual(recipe_id, "authorized-assessment-setup")
        self.assertEqual(scope.step_id, "review-assessment-scope")
        self.assertIn("existing scope dialog", scope.explanation)

    def test_assessment_state_change_requires_framework_confirmation(self):
        recipe = self.by_id["authorized-assessment-setup"]
        scope_index = next(
            index for index, step in enumerate(recipe.steps)
            if step.step_id == "review-assessment-scope"
        )
        controller = RecipeRunController((recipe,))
        controller.start(recipe.recipe_id, self.host)
        for _index in range(scope_index):
            controller.mark_complete(self.host)
            controller.continue_run()
        blocked = controller.run_current(self.host)
        self.assertEqual(blocked.code, "confirmation_required")
        self.assertFalse(self.fixture.calls)
        self.assertTrue(controller.run_current(self.host, confirmed=True).ok)
        self.assertEqual(self.fixture.calls, ["assessment-scope"])

    def test_required_bound_state_is_exact_and_changes_pause(self):
        recipe = self.by_id["instrumentation-session"]
        controller = RecipeRunController((recipe,))
        controller.start(recipe.recipe_id, self.host)
        controller.update_host_state(
            RecipeProjectedState(
                selected_serial="SERIAL-B",
                device_state="device",
                selected_target="org.example.other",
            )
        )
        self.assertEqual(
            controller.state.status, RecipeRunStatus.PAUSED_STATE_CHANGED
        )
        self.assertEqual(controller.state.bound_serial, "SERIAL-A")
        self.assertEqual(controller.state.bound_target, "org.example.fixture")

    def test_run_started_without_device_never_adopts_later_selection(self):
        recipe = self.by_id["device-readiness"]
        controller = RecipeRunController((recipe,))
        controller.start(recipe.recipe_id, RecipeProjectedState())
        controller.mark_complete()
        controller.continue_run()
        controller.mark_complete()
        controller.continue_run()
        result = controller.run_current(self.host)
        self.assertEqual(result.code, "device_binding_required")
        self.assertEqual(controller.state.bound_serial, "")
        controller.restart_with_current_state(self.host)
        self.assertEqual(controller.state.bound_serial, "SERIAL-A")

    def test_guided_and_advanced_descriptions_share_one_recipe_model(self):
        for recipe in self.catalog:
            self.assertTrue(recipe.guided_description)
            self.assertTrue(recipe.advanced_description)
            self.assertIn("serial", recipe.advanced_description.casefold())
            controller = RecipeRunController((recipe,))
            controller.start(recipe.recipe_id, self.host)
            before = controller.state
            advanced = RecipeProjectedState(
                **{
                    name: getattr(self.host, name)
                    for name in self.host.__slots__
                    if name != "interface_mode"
                },
                interface_mode="advanced",
            )
            controller.update_host_state(advanced)
            self.assertEqual(controller.state, before)

    def test_context_help_explains_non_macro_binding_and_cancellation(self):
        topic = HelpRegistry().get("workflow-recipes")
        self.assertIsNotNone(topic)
        text = topic.searchable_text
        for term in (
            "without behaving like automation macros",
            "state-changing",
            "changed or disconnected",
            "cancel",
            "guided",
            "advanced",
        ):
            self.assertIn(term, text)


class WorkflowRecipePaletteIntegrationTests(unittest.TestCase):
    def test_individual_palette_entries_focus_without_starting(self):
        source = (ROOT / "app/gui/main_window.py").read_text()
        self.assertIn('f"recipe.{recipe.recipe_id}"', source)
        self.assertIn("self.open_workflow_recipes(value)", source)
        self.assertIn("Focus only; recipe does not start automatically.", source)
        opener = source.split("def open_workflow_recipes", 1)[1].split(
            "def current_help_topic", 1
        )[0]
        self.assertNotIn(".start(", opener)

    def test_host_adapters_only_open_existing_destinations(self):
        source = (ROOT / "app/gui/main_window.py").read_text()
        for route in (
            "self.device_dock.expand()",
            'self.navigate_workspace("Instrumentation")',
            'center.tabs.set("Frida REPL")',
            'self.navigate_workspace("Pentest")',
            'panel._select_section("Timeline")',
        ):
            self.assertIn(route, source)
        adapter = source.split("def _workflow_recipe_specs", 1)[1].split(
            "def _workflow_recipe_controller", 1
        )[0]
        for prohibited in (
            ".refresh_devices(",
            ".scan(",
            ".launch(",
            ".start(",
            ".install(",
            ".load(",
            "subprocess",
        ):
            self.assertNotIn(prohibited, adapter)


if __name__ == "__main__":
    unittest.main()
