import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from app.core.workflow_recipes import (
    RecipeProjectedState,
    RecipeRunController,
    RecipeRunStatus,
    RecipeSpec,
    RecipeStepResult,
    RecipeStepSpec,
    RecipeStepStatus,
    StepActionClass,
    StepAvailability,
)


ROOT = Path(__file__).parents[1]


def step(
    step_id,
    classification=StepActionClass.INFORMATIONAL,
    *,
    invoke=None,
    optional=False,
    requires_device=False,
    requires_target=False,
    availability=lambda _state: StepAvailability(),
):
    return RecipeStepSpec(
        step_id,
        step_id.replace("-", " ").title(),
        "Review this step.",
        "Prove explicit operator progression.",
        classification,
        requires_device=requires_device,
        requires_target=requires_target,
        optional=optional,
        action_label="Run Check",
        preview_provider=lambda state: f"Device: {state.selected_serial or 'none'}",
        technical_preview_provider=lambda state: (
            f"serial={state.selected_serial or 'none'} "
            f"target={state.selected_target or 'none'}"
        ),
        availability_provider=availability,
        invoke=invoke,
        next_step_guidance="Continue only after reviewing the result.",
    )


def recipe(*steps):
    return RecipeSpec(
        "fixture",
        "Fixture Recipe",
        "A local-only fixture.",
        "Testing",
        "Low",
        ("Explicit operator review",),
        tuple(steps),
        ("fixture", "checklist"),
    )


class WorkflowRecipeModelTests(unittest.TestCase):
    def test_models_are_immutable_and_gui_neutral(self):
        value = recipe(step("explain"))
        with self.assertRaises(FrozenInstanceError):
            value.title = "Changed"
        slots = " ".join((*value.__slots__, *value.steps[0].__slots__))
        self.assertNotIn("widget", slots)
        source = (ROOT / "app/core/workflow_recipes.py").read_text()
        self.assertNotIn("tkinter", source)
        self.assertNotIn("subprocess", source)

    def test_duplicate_recipe_and_step_ids_are_rejected(self):
        value = recipe(step("same"))
        with self.assertRaises(ValueError):
            RecipeRunController((value, value))
        with self.assertRaises(ValueError):
            RecipeRunController((recipe(step("same"), step("same")),))

    def test_every_step_classification_is_representable(self):
        values = tuple(
            step(item.value, item) for item in StepActionClass
        )
        controller = RecipeRunController((recipe(*values),))
        self.assertEqual(
            {item.classification for item in controller.recipes[0].steps},
            set(StepActionClass),
        )


class WorkflowRecipeRunTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.host = RecipeProjectedState(
            selected_serial="SERIAL-A",
            device_name="Fixture",
            device_state="device",
            selected_target="org.example.fixture",
            target_name="Fixture",
            authorization_confirmed=True,
        )

    def action(self, state):
        self.calls.append((state.selected_serial, state.selected_target))
        return RecipeStepResult(True, "One bounded action completed.")

    def controller(self, *steps):
        return RecipeRunController((recipe(*steps),))

    def test_start_binds_state_and_runs_nothing(self):
        controller = self.controller(
            step("check", StepActionClass.READ_ONLY, invoke=self.action)
        )
        state = controller.start("fixture", self.host)
        self.assertEqual(state.status, RecipeRunStatus.ACTIVE)
        self.assertEqual(state.bound_serial, "SERIAL-A")
        self.assertEqual(state.bound_target, "org.example.fixture")
        self.assertFalse(self.calls)

    def test_one_explicit_action_completes_without_auto_advance(self):
        controller = self.controller(
            step("one", StepActionClass.READ_ONLY, invoke=self.action),
            step("two", StepActionClass.READ_ONLY, invoke=self.action),
        )
        controller.start("fixture", self.host)
        result = controller.run_current(self.host)
        self.assertTrue(result.ok)
        self.assertEqual(self.calls, [("SERIAL-A", "org.example.fixture")])
        self.assertEqual(controller.state.current_step_index, 0)
        self.assertEqual(
            controller.state.step_statuses[0], RecipeStepStatus.COMPLETED
        )
        controller.continue_run()
        self.assertEqual(controller.state.current_step_index, 1)
        self.assertEqual(len(self.calls), 1)

    def test_manual_and_informational_steps_require_operator_completion(self):
        for classification in (
            StepActionClass.INFORMATIONAL,
            StepActionClass.MANUAL,
        ):
            controller = self.controller(step("manual", classification))
            controller.start("fixture", self.host)
            result = controller.run_current(self.host)
            self.assertEqual(result.code, "manual_step")
            controller.mark_complete()
            self.assertEqual(
                controller.state.step_statuses[0],
                RecipeStepStatus.COMPLETED,
            )

    def test_navigation_and_read_only_callbacks_are_bounded(self):
        for classification in (
            StepActionClass.NAVIGATION,
            StepActionClass.READ_ONLY,
        ):
            controller = self.controller(
                step("action", classification, invoke=self.action)
            )
            controller.start("fixture", self.host)
            self.assertTrue(controller.run_current(self.host).ok)
        self.assertEqual(len(self.calls), 2)

    def test_state_change_requires_explicit_confirmation(self):
        controller = self.controller(
            step("change", StepActionClass.STATE_CHANGING, invoke=self.action)
        )
        controller.start("fixture", self.host)
        result = controller.run_current(self.host)
        self.assertEqual(result.code, "confirmation_required")
        self.assertFalse(self.calls)
        self.assertTrue(controller.run_current(self.host, confirmed=True).ok)
        self.assertEqual(len(self.calls), 1)

    def test_cancelled_confirmation_performs_no_action(self):
        controller = self.controller(
            step("change", StepActionClass.STATE_CHANGING, invoke=self.action)
        )
        controller.start("fixture", self.host)
        controller.run_current(self.host, confirmed=False)
        self.assertFalse(self.calls)
        self.assertEqual(
            controller.state.step_statuses[0], RecipeStepStatus.PENDING
        )

    def test_required_step_cannot_be_skipped_and_optional_can(self):
        required = self.controller(step("required"))
        required.start("fixture", self.host)
        with self.assertRaises(ValueError):
            required.skip_current()
        optional = self.controller(step("optional", optional=True))
        optional.start("fixture", self.host)
        optional.skip_current()
        self.assertEqual(
            optional.state.step_statuses[0], RecipeStepStatus.SKIPPED
        )

    def test_retry_repeats_only_failed_step(self):
        results = [
            RecipeStepResult(False, "Fixture failure."),
            RecipeStepResult(True, "Fixture recovered."),
        ]
        controller = self.controller(
            step(
                "retry",
                StepActionClass.READ_ONLY,
                invoke=lambda _state: results.pop(0),
            )
        )
        controller.start("fixture", self.host)
        self.assertFalse(controller.run_current(self.host).ok)
        self.assertTrue(controller.retry_current(self.host).ok)
        self.assertEqual(
            controller.state.step_statuses[0], RecipeStepStatus.COMPLETED
        )

    def test_completed_step_remains_complete_when_reviewing_previous(self):
        controller = self.controller(step("one"), step("two"))
        controller.start("fixture", self.host)
        controller.mark_complete()
        controller.continue_run()
        controller.previous_step()
        self.assertEqual(
            controller.state.step_statuses[0], RecipeStepStatus.COMPLETED
        )

    def test_unavailable_step_does_not_invoke(self):
        controller = self.controller(
            step(
                "blocked",
                StepActionClass.READ_ONLY,
                invoke=self.action,
                availability=lambda _state: StepAvailability(
                    False, "Fixture prerequisite missing."
                ),
            )
        )
        controller.start("fixture", self.host)
        result = controller.run_current(self.host)
        self.assertEqual(result.code, "unavailable")
        self.assertFalse(self.calls)

    def test_device_change_disconnect_and_replacement_pause_without_rebind(self):
        controller = self.controller(
            step(
                "device",
                StepActionClass.READ_ONLY,
                invoke=self.action,
                requires_device=True,
            )
        )
        controller.start("fixture", self.host)
        controller.update_host_state(
            RecipeProjectedState(
                selected_serial="SERIAL-B", device_state="device"
            )
        )
        self.assertEqual(
            controller.state.status, RecipeRunStatus.PAUSED_STATE_CHANGED
        )
        self.assertEqual(controller.state.bound_serial, "SERIAL-A")
        self.assertFalse(controller.run_current(self.host).ok)

        controller.restart_with_current_state(self.host)
        controller.update_host_state(
            RecipeProjectedState(
                selected_serial="SERIAL-A", device_state="disconnected"
            )
        )
        self.assertEqual(
            controller.state.status, RecipeRunStatus.PAUSED_STATE_CHANGED
        )

    def test_target_change_pauses_target_bound_recipe(self):
        controller = self.controller(
            step(
                "target",
                StepActionClass.READ_ONLY,
                invoke=self.action,
                requires_target=True,
            )
        )
        controller.start("fixture", self.host)
        controller.update_host_state(
            RecipeProjectedState(
                selected_serial="SERIAL-A",
                device_state="device",
                selected_target="org.example.other",
            )
        )
        self.assertEqual(
            controller.state.status, RecipeRunStatus.PAUSED_STATE_CHANGED
        )
        self.assertEqual(controller.state.bound_target, "org.example.fixture")

    def test_explicit_restart_rebinds_and_resets_progress(self):
        controller = self.controller(step("one"))
        controller.start("fixture", self.host)
        controller.mark_complete()
        other = RecipeProjectedState(
            selected_serial="SERIAL-B", device_state="device"
        )
        controller.restart_with_current_state(other)
        self.assertEqual(controller.state.bound_serial, "SERIAL-B")
        self.assertEqual(
            controller.state.step_statuses, (RecipeStepStatus.PENDING,)
        )

    def test_close_reopen_can_preserve_host_owned_runtime_state(self):
        controller = self.controller(step("one"), step("two"))
        controller.start("fixture", self.host)
        controller.mark_complete()
        received = []
        first = controller.subscribe(received.append)
        first.cancel()
        second = controller.subscribe(received.append)
        self.assertEqual(controller.state.step_statuses[0], RecipeStepStatus.COMPLETED)
        second.cancel()
        self.assertEqual(controller.subscription_count(), 0)

    def test_cancel_and_complete_are_terminal_without_automatic_action(self):
        controller = self.controller(step("one"))
        controller.start("fixture", self.host)
        controller.cancel()
        self.assertEqual(controller.state.status, RecipeRunStatus.CANCELLED)
        self.assertFalse(controller.run_current(self.host).ok)
        controller.restart_with_current_state(self.host)
        controller.mark_complete()
        controller.continue_run()
        self.assertEqual(controller.state.status, RecipeRunStatus.COMPLETED)
        self.assertFalse(self.calls)


class WorkflowRecipeIntegrationSourceTests(unittest.TestCase):
    def test_window_is_lazy_singleton_and_shutdown_owned(self):
        source = (ROOT / "app/gui/main_window.py").read_text()
        constructor = source.split("def _initialize_core_services", 1)[1].split(
            "def _build_device_recovery_workspace", 1
        )[0]
        self.assertIn("self.workflow_recipes_window=None", constructor)
        self.assertIn("self.workflow_recipe_controller=None", constructor)
        self.assertNotIn("WorkflowRecipesWindow(", constructor)
        self.assertIn("def open_workflow_recipes", source)
        self.assertIn("workflow_recipes_window.close()", source)

    def test_menu_and_palette_use_same_safe_host_opener(self):
        menu = (ROOT / "app/gui/menu_bar.py").read_text()
        main = (ROOT / "app/gui/main_window.py").read_text()
        self.assertIn('label="Workflow Recipes"', menu)
        self.assertIn("command=window.open_workflow_recipes", menu)
        self.assertIn('"tool.workflow-recipes"', main)
        self.assertIn("lambda _query:self.open_workflow_recipes()", main)

    def test_recipe_gui_has_no_managers_workers_or_process_access(self):
        source = (ROOT / "app/gui/workflow_recipes_window.py").read_text()
        for name in (
            "DeviceManager",
            "PluginManager",
            "ADBManager",
            "FridaManager",
            "ObjectionManager",
            "BackgroundWorker",
            "subprocess",
        ):
            self.assertNotIn(name, source)
        self.assertNotIn("bind_all(", source)
        self.assertIn("host_subscription.cancel()", source)
        self.assertIn("run_subscription.cancel()", source)

    def test_library_selection_is_separate_from_runtime_start(self):
        source = (ROOT / "app/gui/workflow_recipes_window.py").read_text()
        selection = source.split("def select_recipe", 1)[1].split(
            "def move_selection", 1
        )[0]
        focus_recipe = source.split("def focus_recipe", 1)[1].split(
            "def show_library", 1
        )[0]
        self.assertIn('text="Review"', source)
        self.assertIn('"<Button-1>"', source)
        self.assertIn('"<Double-Button-1>"', source)
        self.assertIn('"<Return>"', source)
        self.assertIn('"<KP_Enter>"', source)
        self.assertIn('"<space>"', source)
        self.assertIn("focus_target = keyboard_focus_target(card)", source)
        keyboard = source.split("if focus_target is not None:", 2)[2].split(
            "self._paint_card", 1
        )[0]
        self.assertIn("focus_target.bind(", keyboard)
        self.assertNotIn("card.bind(", keyboard)
        self.assertIn("self._selected_recipe_id = recipe_id", selection)
        self.assertNotIn("controller.start", selection)
        self.assertNotIn("controller.start", focus_recipe)

    def test_overview_is_the_only_pre_run_start_boundary(self):
        source = (ROOT / "app/gui/workflow_recipes_window.py").read_text()
        overview = source.split("def render_overview", 1)[1].split(
            "def start_selected_recipe", 1
        )[0]
        starter = source.split("def start_selected_recipe", 1)[1].split(
            "def resume_active_recipe", 1
        )[0]
        self.assertIn("Starting this recipe does not run a step.", overview)
        self.assertIn("Ordered step outline", overview)
        self.assertIn("step.classification.display_name", overview)
        self.assertIn("self._live_run()", starter)
        self.assertEqual(starter.count("controller.start"), 1)

    def test_active_footer_uses_progressive_disclosure(self):
        source = (ROOT / "app/gui/workflow_recipes_window.py").read_text()
        footer = source.split("def _render_footer", 1)[1].split(
            "def _active_primary_action", 1
        )[0]
        primary = source.split("def _active_primary_action", 1)[1].split(
            "def _binding_issue", 1
        )[0]
        self.assertIn('"primary"', footer)
        self.assertIn("primary=True", footer)
        self.assertIn("step.optional", footer)
        self.assertIn("state.current_step_index > 0", footer)
        for label in (
            "Run Check",
            "Open Tool",
            "Review Action",
            "Mark Complete",
            "Continue",
            "Retry",
        ):
            self.assertIn(label, primary)
        self.assertNotIn('.configure(state="disabled")', footer)

    def test_active_and_reviewed_recipe_ownership_is_explicit(self):
        source = (ROOT / "app/gui/workflow_recipes_window.py").read_text()
        overview = source.split("def render_overview", 1)[1].split(
            "def start_selected_recipe", 1
        )[0]
        footer = source.split("def _render_footer", 1)[1].split(
            "def _active_primary_action", 1
        )[0]
        self.assertIn("Active recipe:", overview)
        self.assertIn("Only one recipe can be active at a time.", overview)
        self.assertIn("You may review", overview)
        self.assertIn("completing or cancelling", overview)
        self.assertIn('self._named_action("Resume", active.title)', footer)
        self.assertIn('self._named_action("Cancel", active.title, 26)', footer)
        self.assertIn('self._named_action("Start", reviewed.title)', footer)
        self.assertNotIn("controller.start", footer)


if __name__ == "__main__":
    unittest.main()
