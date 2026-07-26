"""GUI-neutral, operator-driven workflow recipe models and run controller."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable, Iterable


class StepActionClass(str, Enum):
    INFORMATIONAL = "informational"
    MANUAL = "manual"
    NAVIGATION = "navigation"
    READ_ONLY = "read_only"
    STATE_CHANGING = "state_changing"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


class RecipeRunStatus(str, Enum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    WAITING_FOR_OPERATOR = "waiting_for_operator"
    RUNNING_STEP = "running_step"
    PAUSED_STATE_CHANGED = "paused_state_changed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class RecipeStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class RecipeProjectedState:
    """The bounded immutable host state visible to recipe providers."""

    selected_serial: str = ""
    device_name: str = ""
    device_state: str = "unavailable"
    selected_target: str = ""
    target_name: str = ""
    assessment_name: str = ""
    authorization_confirmed: bool = False
    session_state: str = "none"
    interface_mode: str = "guided"
    lifecycle: str = "ready"

    @property
    def device_present(self) -> bool:
        return bool(self.selected_serial) and self.device_state not in {
            "disconnected",
            "unavailable",
        }

    @classmethod
    def from_host_snapshot(cls, snapshot) -> "RecipeProjectedState":
        device = getattr(snapshot, "selected_device", None)
        target = getattr(snapshot, "selected_target", None)
        scope = getattr(snapshot, "assessment_scope", None)
        return cls(
            selected_serial=getattr(device, "serial", "") if device else "",
            device_name=(
                getattr(device, "display_name", "")
                or getattr(device, "model", "")
                if device else ""
            ),
            device_state=getattr(device, "state", "unavailable") if device else "unavailable",
            selected_target=(
                getattr(target, "identifier", "")
                or getattr(target, "name", "")
                if target else ""
            ),
            target_name=getattr(target, "name", "") if target else "",
            assessment_name=getattr(scope, "case_name", "") if scope else "",
            authorization_confirmed=bool(
                getattr(scope, "authorization_confirmed", False)
            ),
            session_state=getattr(snapshot, "session_state", "none"),
            interface_mode=getattr(snapshot, "interface_mode", "guided"),
            lifecycle=getattr(snapshot, "lifecycle", "ready"),
        )


@dataclass(frozen=True, slots=True)
class StepAvailability:
    available: bool = True
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class RecipeStepResult:
    ok: bool
    summary: str
    details: str = ""
    next_guidance: str = ""
    code: str = ""


def _available(_state: RecipeProjectedState) -> StepAvailability:
    return StepAvailability()


def _preview(_state: RecipeProjectedState) -> str:
    return "Review this step before continuing."


@dataclass(frozen=True, slots=True)
class RecipeStepSpec:
    step_id: str
    title: str
    explanation: str
    purpose: str
    classification: StepActionClass
    requires_device: bool = False
    requires_target: bool = False
    optional: bool = False
    action_label: str = ""
    preview_provider: Callable[[RecipeProjectedState], str] = field(
        default=_preview, compare=False, repr=False
    )
    technical_preview_provider: Callable[[RecipeProjectedState], str] = field(
        default=_preview, compare=False, repr=False
    )
    availability_provider: Callable[
        [RecipeProjectedState], StepAvailability
    ] = field(default=_available, compare=False, repr=False)
    invoke: Callable[
        [RecipeProjectedState], RecipeStepResult
    ] | None = field(default=None, compare=False, repr=False)
    success_guidance: str = ""
    failure_guidance: str = ""
    next_step_guidance: str = ""

    def availability(self, state: RecipeProjectedState) -> StepAvailability:
        if self.requires_device and not state.device_present:
            return StepAvailability(False, "Select the intended device explicitly.")
        if self.requires_target and not state.selected_target:
            return StepAvailability(False, "Select the intended target explicitly.")
        return self.availability_provider(state)

    def preview(self, state: RecipeProjectedState, advanced=False) -> str:
        provider = (
            self.technical_preview_provider if advanced else self.preview_provider
        )
        return str(provider(state) or "Review this step before continuing.")


@dataclass(frozen=True, slots=True)
class RecipeSpec:
    recipe_id: str
    title: str
    description: str
    category: str
    estimated_complexity: str
    prerequisites: tuple[str, ...]
    steps: tuple[RecipeStepSpec, ...]
    aliases: tuple[str, ...] = ()
    guided_description: str = ""
    advanced_description: str = ""


@dataclass(frozen=True, slots=True)
class RecipeRunState:
    recipe_id: str = ""
    status: RecipeRunStatus = RecipeRunStatus.NOT_STARTED
    current_step_index: int = 0
    bound_serial: str = ""
    bound_target: str = ""
    step_statuses: tuple[RecipeStepStatus, ...] = ()
    step_results: tuple[RecipeStepResult | None, ...] = ()
    message: str = ""


class RecipeRunSubscription:
    def __init__(self, cancel: Callable[[], None]):
        self._cancel = cancel

    def cancel(self) -> None:
        cancel, self._cancel = self._cancel, None
        if cancel:
            cancel()

    close = cancel


class RecipeRunController:
    """Runs at most one explicitly requested step and never auto-advances."""

    def __init__(self, recipes: Iterable[RecipeSpec]):
        values = tuple(recipes)
        identifiers = tuple(recipe.recipe_id for recipe in values)
        if any(not identifier for identifier in identifiers):
            raise ValueError("Recipe IDs must be non-empty.")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Recipe IDs must be unique.")
        for recipe in values:
            step_ids = tuple(step.step_id for step in recipe.steps)
            if not step_ids or any(not value for value in step_ids):
                raise ValueError("Every recipe requires stable, non-empty steps.")
            if len(set(step_ids)) != len(step_ids):
                raise ValueError(f"Recipe {recipe.recipe_id} has duplicate step IDs.")
        self._recipes = values
        self._by_id = {recipe.recipe_id: recipe for recipe in values}
        self._state = RecipeRunState()
        self._listeners: dict[int, Callable[[RecipeRunState], None]] = {}
        self._running = False

    @property
    def recipes(self) -> tuple[RecipeSpec, ...]:
        return self._recipes

    @property
    def state(self) -> RecipeRunState:
        return self._state

    @property
    def active_recipe(self) -> RecipeSpec | None:
        return self._by_id.get(self._state.recipe_id)

    @property
    def current_step(self) -> RecipeStepSpec | None:
        recipe = self.active_recipe
        if recipe is None or not recipe.steps:
            return None
        index = min(max(0, self._state.current_step_index), len(recipe.steps) - 1)
        return recipe.steps[index]

    def subscribe(
        self, callback: Callable[[RecipeRunState], None], *, replay=True
    ) -> RecipeRunSubscription:
        key = id(callback)
        self._listeners[key] = callback
        if replay:
            callback(self._state)
        return RecipeRunSubscription(lambda: self._listeners.pop(key, None))

    def subscription_count(self) -> int:
        return len(self._listeners)

    def _publish(self, state: RecipeRunState) -> RecipeRunState:
        self._state = state
        for callback in tuple(self._listeners.values()):
            callback(state)
        return state

    def start(
        self, recipe_id: str, host_state: RecipeProjectedState
    ) -> RecipeRunState:
        recipe = self._by_id.get(recipe_id)
        if recipe is None:
            raise KeyError(recipe_id)
        return self._publish(
            RecipeRunState(
                recipe_id=recipe_id,
                status=RecipeRunStatus.ACTIVE,
                bound_serial=host_state.selected_serial,
                bound_target=host_state.selected_target,
                step_statuses=tuple(
                    RecipeStepStatus.PENDING for _step in recipe.steps
                ),
                step_results=tuple(None for _step in recipe.steps),
                message=(
                    "Recipe started. No step has run; review the first step."
                ),
            )
        )

    def restart_with_current_state(
        self, host_state: RecipeProjectedState
    ) -> RecipeRunState:
        if not self._state.recipe_id:
            return self._state
        return self.start(self._state.recipe_id, host_state)

    def update_host_state(
        self, host_state: RecipeProjectedState
    ) -> RecipeRunState:
        recipe = self.active_recipe
        if recipe is None or self._state.status in {
            RecipeRunStatus.CANCELLED,
            RecipeRunStatus.COMPLETED,
            RecipeRunStatus.NOT_STARTED,
        }:
            return self._state
        device_dependent = any(step.requires_device for step in recipe.steps)
        target_dependent = any(step.requires_target for step in recipe.steps)
        reason = ""
        if device_dependent and self._state.bound_serial:
            if (
                host_state.selected_serial != self._state.bound_serial
                or not host_state.device_present
            ):
                reason = (
                    "The bound device changed or disappeared. This run remains "
                    f"bound to {self._state.bound_serial}; restart explicitly to rebind."
                )
        if not reason and target_dependent and self._state.bound_target:
            if host_state.selected_target != self._state.bound_target:
                reason = (
                    "The bound target changed or disappeared. This run remains "
                    f"bound to {self._state.bound_target}; restart explicitly to rebind."
                )
        if reason:
            return self._publish(
                replace(
                    self._state,
                    status=RecipeRunStatus.PAUSED_STATE_CHANGED,
                    message=reason,
                )
            )
        return self._state

    def _replace_current(
        self,
        *,
        step_status: RecipeStepStatus | None = None,
        result: RecipeStepResult | None = None,
        status: RecipeRunStatus | None = None,
        message: str | None = None,
    ) -> RecipeRunState:
        index = self._state.current_step_index
        statuses = list(self._state.step_statuses)
        results = list(self._state.step_results)
        if step_status is not None and statuses:
            statuses[index] = step_status
        if result is not None and results:
            results[index] = result
        return self._publish(
            replace(
                self._state,
                status=status or self._state.status,
                step_statuses=tuple(statuses),
                step_results=tuple(results),
                message=self._state.message if message is None else message,
            )
        )

    def run_current(
        self,
        host_state: RecipeProjectedState,
        *,
        confirmed=False,
    ) -> RecipeStepResult:
        step = self.current_step
        if step is None:
            return RecipeStepResult(False, "No active recipe step.", code="no_step")
        if self._running or self._state.status is RecipeRunStatus.RUNNING_STEP:
            return RecipeStepResult(
                False, "Another recipe step is already running.", code="busy"
            )
        if self._state.status is RecipeRunStatus.PAUSED_STATE_CHANGED:
            return RecipeStepResult(
                False, self._state.message, code="state_changed"
            )
        if self._state.status in {
            RecipeRunStatus.CANCELLED,
            RecipeRunStatus.COMPLETED,
            RecipeRunStatus.NOT_STARTED,
        }:
            return RecipeStepResult(
                False, "This recipe is not active.", code="inactive"
            )
        availability = step.availability(host_state)
        if not availability.available:
            result = RecipeStepResult(
                False,
                availability.explanation or "This step is unavailable.",
                step.failure_guidance,
                code="unavailable",
            )
            self._replace_current(
                step_status=RecipeStepStatus.FAILED,
                result=result,
                status=RecipeRunStatus.WAITING_FOR_OPERATOR,
                message=result.summary,
            )
            return result
        if step.classification is StepActionClass.STATE_CHANGING and not confirmed:
            return RecipeStepResult(
                False,
                "Explicit confirmation is required before this state-changing step.",
                step.preview(host_state, advanced=True),
                code="confirmation_required",
            )
        if step.invoke is None:
            return RecipeStepResult(
                False,
                "This step is completed manually by the operator.",
                code="manual_step",
            )
        self._running = True
        self._replace_current(
            step_status=RecipeStepStatus.RUNNING,
            status=RecipeRunStatus.RUNNING_STEP,
            message=f"Running only: {step.title}",
        )
        try:
            value = step.invoke(host_state)
            if not isinstance(value, RecipeStepResult):
                raise TypeError("Recipe callbacks must return RecipeStepResult.")
        except Exception as exc:
            value = RecipeStepResult(
                False,
                f"{step.title} failed.",
                f"{type(exc).__name__}: {exc}",
                step.failure_guidance,
                "exception",
            )
        finally:
            self._running = False
        self._replace_current(
            step_status=(
                RecipeStepStatus.COMPLETED
                if value.ok else RecipeStepStatus.FAILED
            ),
            result=value,
            status=RecipeRunStatus.WAITING_FOR_OPERATOR,
            message=value.summary,
        )
        return value

    def mark_complete(self) -> RecipeRunState:
        step = self.current_step
        if step is None:
            return self._state
        result = RecipeStepResult(
            True,
            f"{step.title} marked complete by the operator.",
            next_guidance=step.next_step_guidance,
            code="operator_complete",
        )
        return self._replace_current(
            step_status=RecipeStepStatus.COMPLETED,
            result=result,
            status=RecipeRunStatus.WAITING_FOR_OPERATOR,
            message=result.summary,
        )

    def retry_current(
        self,
        host_state: RecipeProjectedState,
        *,
        confirmed=False,
    ) -> RecipeStepResult:
        if (
            not self._state.step_statuses
            or self._state.step_statuses[self._state.current_step_index]
            is not RecipeStepStatus.FAILED
        ):
            return RecipeStepResult(False, "Only a failed step can be retried.")
        self._replace_current(
            step_status=RecipeStepStatus.PENDING,
            status=RecipeRunStatus.WAITING_FOR_OPERATOR,
            message="Retry explicitly requested.",
        )
        return self.run_current(host_state, confirmed=confirmed)

    def skip_current(self) -> RecipeRunState:
        step = self.current_step
        if step is None or not step.optional:
            raise ValueError("Required recipe steps cannot be skipped.")
        result = RecipeStepResult(
            True, f"{step.title} skipped by the operator.", code="operator_skipped"
        )
        return self._replace_current(
            step_status=RecipeStepStatus.SKIPPED,
            result=result,
            status=RecipeRunStatus.WAITING_FOR_OPERATOR,
            message=result.summary,
        )

    def continue_run(self) -> RecipeRunState:
        recipe = self.active_recipe
        if recipe is None:
            return self._state
        current = self._state.step_statuses[self._state.current_step_index]
        if current not in {
            RecipeStepStatus.COMPLETED,
            RecipeStepStatus.SKIPPED,
        }:
            raise ValueError("Complete or skip the current step before continuing.")
        next_index = self._state.current_step_index + 1
        if next_index >= len(recipe.steps):
            return self._publish(
                replace(
                    self._state,
                    status=RecipeRunStatus.COMPLETED,
                    message="Recipe completed by explicit operator progression.",
                )
            )
        return self._publish(
            replace(
                self._state,
                current_step_index=next_index,
                status=RecipeRunStatus.WAITING_FOR_OPERATOR,
                message="Review the next step; it has not run.",
            )
        )

    def previous_step(self) -> RecipeRunState:
        if self.active_recipe is None:
            return self._state
        return self._publish(
            replace(
                self._state,
                current_step_index=max(0, self._state.current_step_index - 1),
                status=RecipeRunStatus.WAITING_FOR_OPERATOR,
                message="Reviewing a previous step; no action was run.",
            )
        )

    def cancel(self) -> RecipeRunState:
        if self.active_recipe is None:
            return self._state
        return self._publish(
            replace(
                self._state,
                status=RecipeRunStatus.CANCELLED,
                message="Recipe cancelled. No additional step will run.",
            )
        )
