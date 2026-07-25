"""Deterministic, non-executing guide plans from structured host state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GuideGoal(str, Enum):
    SEE_INSTALLED_APPS = "See installed applications"
    OBSERVE_RUNNING = "Observe an app already running"
    START_UNDER_FRIDA = "Start an app under Frida"
    LOAD_SCRIPT = "Load a Frida script"
    LEARN_OBJECTION = "Learn Objection"
    RECOVER_FILES = "Recover selected files"
    CHECK_READINESS = "Check Frida readiness"
    INSPECT_WEBVIEWS = "Inspect WebViews"
    OPEN_ADB_SHELL = "Open an ADB shell"


class InstrumentationRoute(str, Enum):
    ROOTED_SERVER_READY = "ROOTED_SERVER_READY"
    ROOTED_SERVER_SETUP_AVAILABLE = "ROOTED_SERVER_SETUP_AVAILABLE"
    GADGET_READY = "GADGET_READY"
    GADGET_PREPARATION_AVAILABLE = "GADGET_PREPARATION_AVAILABLE"
    DEBUGGABLE_DEVELOPMENT_ROUTE = "DEBUGGABLE_DEVELOPMENT_ROUTE"
    EMULATOR_ROUTE = "EMULATOR_ROUTE"
    ADB_ONLY = "ADB_ONLY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class GuideState:
    selected_serial: str = ""
    adb_state: str = "unavailable"
    host_frida_available: bool = False
    frida_endpoint_reachable: bool = False
    root_available: bool = False
    server_available: bool = False
    gadget_available: bool = False
    debuggable: bool = False
    emulator: bool = False
    installed_apps_scanned: bool = False
    selected_package: str = ""
    selected_target: str = ""
    selected_script: str = ""
    advisor_available: bool = False
    rescue_available: bool = False
    webview_available: bool = False

    @property
    def adb_usable(self) -> bool:
        return bool(self.selected_serial) and self.adb_state in {
            "device", "recovery", "sideload"
        }


@dataclass(frozen=True, slots=True)
class GuideAction:
    label: str
    destination: str
    explanation: str
    prerequisites: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GuidePlan:
    goal: GuideGoal
    route: InstrumentationRoute
    summary: str
    actions: tuple[GuideAction, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    executes_automatically: bool = False


class GuideEngine:
    def determine_route(self, state: GuideState) -> InstrumentationRoute:
        if not state.selected_serial:
            return InstrumentationRoute.UNKNOWN
        if not state.adb_usable:
            return InstrumentationRoute.BLOCKED
        if state.root_available and state.server_available and state.frida_endpoint_reachable:
            return InstrumentationRoute.ROOTED_SERVER_READY
        if state.root_available and not state.server_available:
            return InstrumentationRoute.ROOTED_SERVER_SETUP_AVAILABLE
        if state.gadget_available and state.frida_endpoint_reachable:
            return InstrumentationRoute.GADGET_READY
        if state.gadget_available or state.selected_package:
            return InstrumentationRoute.GADGET_PREPARATION_AVAILABLE
        if state.debuggable:
            return InstrumentationRoute.DEBUGGABLE_DEVELOPMENT_ROUTE
        if state.emulator:
            return InstrumentationRoute.EMULATOR_ROUTE
        if state.adb_usable:
            return InstrumentationRoute.ADB_ONLY
        return InstrumentationRoute.UNKNOWN

    def plan(self, goal: GuideGoal | str, state: GuideState) -> GuidePlan:
        selected_goal = GuideGoal(goal)
        route = self.determine_route(state)
        actions = []
        blockers = []
        warnings = []
        if not state.selected_serial:
            blockers.append("Select a device explicitly.")
            actions.append(
                GuideAction(
                    "Select Device", "console",
                    "Refresh devices and explicitly select the intended serial.",
                )
            )
        elif not state.adb_usable:
            blockers.append(
                f"The selected device ADB state is {state.adb_state}."
            )
            actions.append(
                GuideAction(
                    "Check ADB", "instrumentation-overview",
                    "Resolve authorization or connectivity without switching serials.",
                )
            )

        if selected_goal is GuideGoal.SEE_INSTALLED_APPS:
            if state.adb_usable:
                actions.append(
                    GuideAction(
                        "Scan Installed Apps", "targets-installed",
                        "Use the ADB-backed application scan; Frida is not required.",
                    )
                )
        elif selected_goal is GuideGoal.OBSERVE_RUNNING:
            actions.extend(self._runtime_actions(state, spawn=False))
        elif selected_goal is GuideGoal.START_UNDER_FRIDA:
            actions.extend(self._runtime_actions(state, spawn=True))
        elif selected_goal is GuideGoal.LOAD_SCRIPT:
            if not state.selected_script:
                actions.append(
                    GuideAction(
                        "Select Script Studio Script", "script-studio",
                        "Review and select a local script; it will not load automatically.",
                    )
                )
            actions.extend(self._runtime_actions(state, spawn=False))
            actions.append(
                GuideAction(
                    "Review Load", "script-studio",
                    "Validate and explicitly load or reload the selected script.",
                )
            )
        elif selected_goal is GuideGoal.LEARN_OBJECTION:
            actions.append(
                GuideAction(
                    "Open Learning Center", "learning-center",
                    "Open Objection Assistant and use its local Learn section with synthetic practice.",
                )
            )
            if state.frida_endpoint_reachable:
                actions.append(
                    GuideAction(
                        "Review Objection Session", "sessions-center",
                        "Review attach or spawn arguments without launching automatically.",
                    )
                )
        elif selected_goal is GuideGoal.RECOVER_FILES:
            actions.append(
                GuideAction(
                    "Open Device Rescue", "device-rescue",
                    "Scan and plan explicitly selected-file recovery. No source files are deleted.",
                )
            )
            warnings.append(
                "Bootloader unlocking commonly wipes user data and must not be used as a recovery technique."
            )
        elif selected_goal is GuideGoal.CHECK_READINESS:
            actions.append(
                GuideAction(
                    "Open Readiness Advisor", "readiness-advisor",
                    "Review evidence and available routes without acquiring root.",
                )
            )
        elif selected_goal is GuideGoal.INSPECT_WEBVIEWS:
            actions.append(
                GuideAction(
                    "Open WebView Inspector", "webview-inspector",
                    "Begin with static candidates; runtime observation remains explicit.",
                )
            )
        elif selected_goal is GuideGoal.OPEN_ADB_SHELL:
            if state.adb_usable:
                actions.append(
                    GuideAction(
                        "Review ADB Shell", "sessions-center",
                        "Open a dedicated shell bound to the selected serial.",
                    )
                )

        summary = (
            f"Available route: {route.value}. "
            "The guide returns reviewable next actions and never executes them."
        )
        return GuidePlan(
            selected_goal,
            route,
            summary,
            tuple(actions),
            tuple(blockers),
            tuple(warnings),
        )

    @staticmethod
    def _runtime_actions(state: GuideState, *, spawn: bool):
        actions = []
        if not state.installed_apps_scanned:
            actions.append(
                GuideAction(
                    "Scan Installed Apps", "targets-installed",
                    "Find packages over ADB before choosing a target.",
                )
            )
        if not state.selected_package and not state.selected_target:
            actions.append(
                GuideAction(
                    "Select App", "targets",
                    "Choose the intended package or running process explicitly.",
                )
            )
        if not state.frida_endpoint_reachable:
            actions.append(
                GuideAction(
                    "Check Frida Readiness", "readiness-advisor",
                    "Review available Server, Gadget, development, emulator, or ADB-only routes.",
                )
            )
        else:
            actions.append(
                GuideAction(
                    "Review Start and Observe App" if spawn else "Review Observe Running App",
                    "sessions-center",
                    "Review the dedicated session plan; no attach or spawn occurs automatically.",
                )
            )
        return actions
