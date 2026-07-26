"""Host-owned v1 workflow recipe catalog built from narrow safe callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.workflow_recipes import (
    RecipeProjectedState,
    RecipeSpec,
    RecipeStepResult,
    RecipeStepSpec,
    StepActionClass,
    StepAvailability,
)


HostCallback = Callable[[], object]


@dataclass(frozen=True, slots=True)
class RecipeHostCallbacks:
    """Navigation-only adapters supplied by the application host."""

    focus_device_selector: HostCallback
    open_environment_diagnostics: HostCallback
    open_installed_applications: HostCallback
    open_readiness_advisor: HostCallback
    open_frida_assistant: HostCallback
    open_frida_sessions: HostCallback
    open_device_recovery: HostCallback
    open_pentest: HostCallback
    open_assessment_scope: HostCallback
    open_findings: HostCallback
    open_timeline: HostCallback


def _open(callback: HostCallback, summary: str, guidance="") -> HostCallback:
    def invoke(_state):
        value = callback()
        if value is False:
            return RecipeStepResult(
                False,
                f"{summary} could not be opened.",
                next_guidance=guidance,
                code="host_route_unavailable",
            )
        return RecipeStepResult(
            True, summary, next_guidance=guidance, code="host_route_opened"
        )

    return invoke


def _device_availability(state: RecipeProjectedState) -> StepAvailability:
    if not state.selected_serial:
        return StepAvailability(False, "Select one device explicitly.")
    return StepAvailability()


def _target_availability(state: RecipeProjectedState) -> StepAvailability:
    if not state.selected_target:
        return StepAvailability(False, "Select one target/package explicitly.")
    return StepAvailability()


def _authorization_availability(
    state: RecipeProjectedState,
) -> StepAvailability:
    if not state.authorization_confirmed:
        return StepAvailability(
            False, "Confirm the authorized assessment scope first."
        )
    return StepAvailability()


def _device_preview(state: RecipeProjectedState) -> str:
    return (
        f"Review the explicitly selected device: "
        f"{state.device_name or state.selected_serial or 'none'}."
    )


def _device_technical_preview(state: RecipeProjectedState) -> str:
    return (
        f"serial={state.selected_serial or 'none'} "
        f"adb_state={state.device_state or 'unavailable'}"
    )


def _target_preview(state: RecipeProjectedState) -> str:
    return (
        "Review the explicitly selected target: "
        f"{state.target_name or state.selected_target or 'none'}."
    )


def _target_technical_preview(state: RecipeProjectedState) -> str:
    return (
        f"serial={state.selected_serial or 'none'} "
        f"package_or_target={state.selected_target or 'none'}"
    )


def _known_device_result(state: RecipeProjectedState) -> RecipeStepResult:
    labels = {
        "device": "online and authorized",
        "unauthorized": "connected but awaiting device authorization",
        "offline": "offline",
        "recovery": "in recovery with bounded ADB access",
        "sideload": "in sideload mode with limited ADB access",
        "bootloader": "in bootloader mode; normal ADB is unavailable",
    }
    current = labels.get(state.device_state, state.device_state or "unavailable")
    ready = state.device_state in {"device", "recovery", "sideload"}
    return RecipeStepResult(
        ready,
        f"Known selected-device state: {current}.",
        (
            f"Serial {state.selected_serial or 'none'} remains the only bound device."
        ),
        (
            "Continue to the next reviewed step."
            if ready else
            "Resolve the displayed state explicitly; no connection or reboot was attempted."
        ),
        "known_device_ready" if ready else "known_device_not_ready",
    )


def _known_target_result(state: RecipeProjectedState) -> RecipeStepResult:
    if not state.selected_target:
        return RecipeStepResult(
            False,
            "No target/package is selected.",
            next_guidance="Choose the intended target explicitly.",
            code="target_missing",
        )
    return RecipeStepResult(
        True,
        f"Target retained: {state.target_name or state.selected_target}.",
        f"Identifier: {state.selected_target}",
        "Continue only if this is the authorized target.",
        "target_confirmed",
    )


def _known_scope_result(state: RecipeProjectedState) -> RecipeStepResult:
    if not state.authorization_confirmed:
        return RecipeStepResult(
            False,
            "Authorization is not confirmed in the active assessment.",
            next_guidance="Open Scope and confirm the authorized boundaries.",
            code="scope_unconfirmed",
        )
    return RecipeStepResult(
        True,
        f"Authorized scope is confirmed for {state.assessment_name or 'the active assessment'}.",
        next_guidance="Continue to review evidence and timeline locations.",
        code="scope_confirmed",
    )


def _step(
    step_id,
    title,
    explanation,
    purpose,
    classification,
    *,
    action_label="",
    callback=None,
    invoke=None,
    requires_device=False,
    requires_target=False,
    optional=False,
    availability=None,
    preview=None,
    technical_preview=None,
    next_guidance="Review the result, then choose Continue explicitly.",
):
    if callback is not None:
        invoke = _open(callback, f"{title} opened.", next_guidance)
    return RecipeStepSpec(
        step_id,
        title,
        explanation,
        purpose,
        classification,
        requires_device=requires_device,
        requires_target=requires_target,
        optional=optional,
        action_label=action_label,
        preview_provider=preview or _device_preview,
        technical_preview_provider=technical_preview or _device_technical_preview,
        availability_provider=availability or (
            _target_availability if requires_target
            else _device_availability if requires_device
            else lambda _state: StepAvailability()
        ),
        invoke=invoke,
        success_guidance=next_guidance,
        failure_guidance="Resolve the displayed prerequisite and retry explicitly.",
        next_step_guidance=next_guidance,
    )


def _recipe(
    recipe_id,
    title,
    description,
    category,
    complexity,
    prerequisites,
    aliases,
    steps,
    advanced,
):
    return RecipeSpec(
        recipe_id,
        title,
        description,
        category,
        complexity,
        tuple(prerequisites),
        tuple(steps),
        tuple(aliases),
        guided_description=description,
        advanced_description=advanced,
    )


def build_recipe_catalog(callbacks: RecipeHostCallbacks) -> tuple[RecipeSpec, ...]:
    """Build five immutable recipes without running any callback."""

    device_readiness = _recipe(
        "device-readiness",
        "Device Readiness",
        "Prepare one explicitly selected Android device for normal SUS Companion use.",
        "Device",
        "Low",
        ("Device ownership", "USB connection", "Explicit device selection"),
        ("device setup", "adb readiness", "usb debugging", "authorization"),
        (
            _step(
                "understand-device-access",
                "Understand USB debugging and authorization",
                "Review why USB debugging, the device authorization prompt, and explicit serial selection matter.",
                "Prevent accidental work against an unintended device.",
                StepActionClass.INFORMATIONAL,
            ),
            _step(
                "open-device-selector",
                "Open the device selector",
                "Open the existing selector without refreshing or selecting anything.",
                "Keep device choice explicit.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.focus_device_selector,
                next_guidance="Choose one device in the existing selector, then return.",
            ),
            _step(
                "review-device-state",
                "Review the known ADB state",
                "Interpret the already-published device state without connecting, authorizing, or rebooting.",
                "Distinguish online, unauthorized, offline, recovery, sideload, and bootloader states.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_device_result,
                requires_device=True,
            ),
            _step(
                "open-host-diagnostics",
                "Open Environment Diagnostics",
                "Open existing local host diagnostics for ADB executable or environment issues.",
                "Separate host-tool problems from device authorization problems.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_environment_diagnostics,
                optional=True,
            ),
            _step(
                "review-device-guidance",
                "Review the recommended device next step",
                "Compare the displayed ADB state with the guidance from diagnostics.",
                "Let the operator decide the next explicit device action.",
                StepActionClass.MANUAL,
            ),
            _step(
                "summarize-device-readiness",
                "Summarize device readiness",
                "Record whether the bound device is ready or which prerequisite remains.",
                "End with a reviewable operator conclusion.",
                StepActionClass.MANUAL,
                requires_device=True,
            ),
        ),
        "Shows the full serial and exact known ADB state; it never issues an ADB command.",
    )

    frida_readiness = _recipe(
        "frida-readiness",
        "Frida Readiness",
        "Determine which existing Frida route is available without starting or modifying anything.",
        "Instrumentation",
        "Medium",
        ("Authorized device if device checks are needed", "Explicit target when relevant"),
        ("frida setup", "frida readiness", "server", "gadget", "attach", "spawn"),
        (
            _step(
                "understand-frida-routes",
                "Understand Server, Gadget, attach, and spawn",
                "Review the difference between device routes and process-start choices.",
                "Avoid treating Frida readiness as automatic execution.",
                StepActionClass.INFORMATIONAL,
            ),
            _step(
                "open-frida-host-diagnostics",
                "Check the host Frida path",
                "Open existing Environment Diagnostics for the local Frida executable.",
                "Review host availability without starting Frida.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_environment_diagnostics,
            ),
            _step(
                "confirm-frida-device",
                "Confirm the selected device",
                "Review the device already selected in SUS Companion.",
                "Bind later readiness review to one exact serial.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_device_result,
                requires_device=True,
            ),
            _step(
                "open-readiness-advisor",
                "Open the Instrumentation & Root Readiness Advisor",
                "Open or focus the existing advisor without running an assessment automatically.",
                "Reuse the established evidence and route presentation.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_readiness_advisor,
            ),
            _step(
                "review-frida-route",
                "Review route, endpoint, forwarding, and runtime state",
                "Use the advisor to review Server, Gadget, endpoint, and forwarding evidence.",
                "Keep route selection and remediation explicit.",
                StepActionClass.MANUAL,
                requires_device=True,
            ),
            _step(
                "open-frida-assistant",
                "Open Frida Assistant",
                "Open or focus the existing assistant for the next explicit action.",
                "Hand off without starting a server, forwarding, attaching, or spawning.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_frida_assistant,
            ),
            _step(
                "summarize-frida-readiness",
                "Summarize Frida readiness",
                "Record the available route and unresolved prerequisites.",
                "Stop before any runtime action.",
                StepActionClass.MANUAL,
            ),
        ),
        "Shows exact serial, target, route terminology, and existing diagnostic destinations.",
    )

    instrumentation_session = _recipe(
        "instrumentation-session",
        "Start an Instrumentation Session",
        "Guide an operator from selected device and target to the existing session screen.",
        "Instrumentation",
        "Medium",
        ("Authorized device", "Explicit target", "Reviewed Frida route"),
        ("session setup", "instrumentation session", "frida session", "target setup"),
        (
            _step(
                "confirm-session-device",
                "Confirm the session device",
                "Review the exact selected device.",
                "Prevent session planning from moving to another serial.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_device_result,
                requires_device=True,
            ),
            _step(
                "open-installed-applications",
                "Open Installed Applications",
                "Open the existing Instrumentation target view; use its explicit scan control if needed.",
                "Reuse target discovery without starting a scan from the recipe.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_installed_applications,
            ),
            _step(
                "confirm-session-target",
                "Confirm the target package",
                "Review the package or target selected through the existing workflow.",
                "Bind the plan to one explicit target.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_target_result,
                requires_device=True,
                requires_target=True,
                preview=_target_preview,
                technical_preview=_target_technical_preview,
            ),
            _step(
                "review-session-readiness",
                "Review Frida readiness",
                "Open the existing advisor before choosing a session route.",
                "Confirm prerequisites without starting or modifying Frida.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_readiness_advisor,
            ),
            _step(
                "choose-attach-or-spawn",
                "Choose attach or spawn",
                "Review whether to observe a running target or start it under instrumentation.",
                "Make the process-start decision explicit.",
                StepActionClass.MANUAL,
                requires_target=True,
                preview=_target_preview,
                technical_preview=_target_technical_preview,
            ),
            _step(
                "open-frida-sessions",
                "Open Sessions Center in Frida mode",
                "Open the existing Frida session page without building or launching a session.",
                "Hand off to the established preview and confirmation flow.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_frida_sessions,
            ),
            _step(
                "stop-before-session-launch",
                "Stop at session launch confirmation",
                "Review the selected serial, target, mode, and command preview in Sessions Center.",
                "Never launch a session from the recipe.",
                StepActionClass.MANUAL,
                requires_device=True,
                requires_target=True,
                preview=_target_preview,
                technical_preview=_target_technical_preview,
            ),
            _step(
                "summarize-session-plan",
                "Summarize the session plan",
                "Record the bound serial, package, route, and attach/spawn choice.",
                "End before the existing launch confirmation.",
                StepActionClass.MANUAL,
                requires_device=True,
                requires_target=True,
                preview=_target_preview,
                technical_preview=_target_technical_preview,
            ),
        ),
        "Shows the exact serial and package identifier and stops before session launch.",
    )

    recovery_preparation = _recipe(
        "broken-screen-recovery",
        "Broken-Screen Recovery Preparation",
        "Prepare a safe selected-file recovery plan without beginning a copy.",
        "Recovery",
        "Medium",
        ("Device ownership", "USB authorization", "Unlocked accessible data", "Destination free space"),
        ("broken screen", "data recovery", "recovery preparation", "storage rescue"),
        (
            _step(
                "understand-recovery-limits",
                "Understand recovery prerequisites",
                "Review ownership, USB authorization, encryption, unlock, and destination-space limits.",
                "Prevent unsafe assumptions about inaccessible encrypted data.",
                StepActionClass.INFORMATIONAL,
            ),
            _step(
                "confirm-recovery-device",
                "Confirm the recovery device",
                "Review the exact selected serial.",
                "Bind recovery preparation to one device only.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_device_result,
                requires_device=True,
            ),
            _step(
                "review-storage-visibility",
                "Review known ADB storage visibility",
                "Interpret the known ADB state before opening the storage scanner.",
                "Avoid running a scan against an unavailable or different device.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_device_result,
                requires_device=True,
            ),
            _step(
                "open-device-recovery",
                "Open Device Rescue & Recovery",
                "Open or focus the existing bounded selected-file recovery workspace.",
                "Reuse its serial guard, scan, destination, and queue controls.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_device_recovery,
            ),
            _step(
                "run-storage-scan-manually",
                "Run Storage Scan in Device Rescue",
                "Use the existing explicit Scan Storage button and wait for its bounded result.",
                "Keep the ADB inventory action operator initiated.",
                StepActionClass.MANUAL,
                requires_device=True,
            ),
            _step(
                "review-recovery-space",
                "Review source estimate and destination free space",
                "Review the existing recovery preflight and safety headroom.",
                "Avoid queuing a copy that cannot fit safely.",
                StepActionClass.MANUAL,
                requires_device=True,
            ),
            _step(
                "plan-small-test-copy",
                "Plan a small test copy",
                "Choose a bounded representative file before considering a larger queue.",
                "Reduce recovery risk without copying anything yet.",
                StepActionClass.MANUAL,
                requires_device=True,
            ),
            _step(
                "stop-before-copy-queue",
                "Stop before queue execution",
                "Review the final source, destination, limits, and exact serial.",
                "Leave copy execution to the existing explicit queue action.",
                StepActionClass.MANUAL,
                requires_device=True,
            ),
        ),
        "Shows the full serial and recovery preflight concepts; never pulls, deletes, roots, unlocks, or flashes.",
    )

    assessment_setup = _recipe(
        "authorized-assessment-setup",
        "Authorized App Assessment Setup",
        "Prepare an authorized assessment without beginning testing actions.",
        "Assessment",
        "Medium",
        ("Explicit authorization", "Selected device", "Selected target package"),
        ("assessment setup", "authorized assessment", "scope checklist", "pentest setup"),
        (
            _step(
                "review-authorization",
                "Review authorization and scope",
                "Confirm that ownership or written authorization and boundaries are understood.",
                "Keep all later actions within an explicit scope.",
                StepActionClass.INFORMATIONAL,
            ),
            _step(
                "confirm-assessment-device",
                "Confirm the assessment device",
                "Review the exact selected device.",
                "Bind the setup to one serial.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_device_result,
                requires_device=True,
            ),
            _step(
                "confirm-assessment-target",
                "Confirm the assessment package",
                "Review the selected target/package.",
                "Bind the setup to the authorized application.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_target_result,
                requires_device=True,
                requires_target=True,
                preview=_target_preview,
                technical_preview=_target_technical_preview,
            ),
            _step(
                "open-pentest-workspace",
                "Open the Pentest workspace",
                "Navigate through the canonical principal-workspace controller.",
                "Use the established assessment state and panels.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_pentest,
            ),
            _step(
                "review-assessment-scope",
                "Review or create assessment scope",
                "Open the existing scope dialog; saving remains a separate explicit confirmation.",
                "Use the established case and authorization lifecycle.",
                StepActionClass.STATE_CHANGING,
                action_label="Review Action",
                callback=callbacks.open_assessment_scope,
                requires_device=True,
                requires_target=True,
                preview=_target_preview,
                technical_preview=_target_technical_preview,
            ),
            _step(
                "confirm-saved-scope",
                "Confirm the active authorized scope",
                "Review the immutable host projection after the existing scope UI is completed.",
                "Verify authorization before any testing action.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=_known_scope_result,
                availability=_authorization_availability,
            ),
            _step(
                "open-findings-guidance",
                "Open Findings guidance",
                "Open the existing Findings area to review local evidence and report locations.",
                "Prepare documentation without creating a finding automatically.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_findings,
            ),
            _step(
                "open-timeline-guidance",
                "Open Timeline guidance",
                "Open the existing Timeline to review assessment event recording.",
                "Prepare review paths without running a test.",
                StepActionClass.NAVIGATION,
                action_label="Open Tool",
                callback=callbacks.open_timeline,
            ),
            _step(
                "summarize-assessment-setup",
                "Summarize prepared assessment state",
                "Record the bound serial, target, scope, and documentation locations.",
                "End before scans, instrumentation, interception, scripts, or tests.",
                StepActionClass.MANUAL,
                requires_device=True,
                requires_target=True,
                preview=_target_preview,
                technical_preview=_target_technical_preview,
            ),
        ),
        "Shows full serial, package ID, assessment name, and exact state-changing classification.",
    )

    return (
        device_readiness,
        frida_readiness,
        instrumentation_session,
        recovery_preparation,
        assessment_setup,
    )
