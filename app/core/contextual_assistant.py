"""GUI-neutral composition for the official Frida and Objection assistants."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.frida_target import FridaTarget, TargetType


@dataclass(frozen=True, slots=True)
class AssistantState:
    kind: str
    serial: str = ""
    device: str = "No device selected"
    adb_state: str = "unavailable"
    target: str = ""
    pid: int | None = None
    interface_mode: str = "guided"
    endpoint: str = "127.0.0.1:27042"

    @property
    def recommended_next_step(self) -> str:
        if not self.serial:
            return "Select and authorize a device, or use Learn and local host-tool checks."
        if self.adb_state not in {"device", "recovery", "sideload"}:
            return f"Resolve the selected device's {self.adb_state} ADB state."
        if not self.target:
            return "Scan or select an application target before preparing a session."
        return "Review a command preview, then hand off to Sessions Center."


@dataclass(frozen=True, slots=True)
class AssistantOperation:
    ok: bool
    title: str
    detail: str = ""
    value: object = None


class ContextualAssistantService:
    """Delegates explicit assistant operations to existing shared services."""

    def __init__(
        self,
        installed_apps,
        target_discovery,
        tool_diagnostics,
        frida_manager,
        interactive_sessions,
        script_library,
        *,
        selected_target_provider=lambda: None,
    ):
        self.installed_apps = installed_apps
        self.target_discovery = target_discovery
        self.tool_diagnostics = tool_diagnostics
        self.frida_manager = frida_manager
        self.interactive_sessions = interactive_sessions
        self.script_library = script_library
        self.selected_target_provider = selected_target_provider

    @staticmethod
    def state(kind, context) -> AssistantState:
        device = dict(getattr(context, "selected_device", {}) or {})
        target = dict(getattr(context, "selected_target", {}) or {})
        return AssistantState(
            kind=str(kind),
            serial=str(device.get("serial", "")),
            device=str(
                device.get("display_name")
                or device.get("model")
                or "No device selected"
            ),
            adb_state=str(getattr(context, "adb_state", "unavailable")),
            target=str(target.get("identifier") or target.get("name") or ""),
            pid=target.get("pid") if isinstance(target.get("pid"), int) else None,
            interface_mode=str(getattr(context, "interface_mode", "guided")),
        )

    def scan_installed(self, state: AssistantState) -> AssistantOperation:
        result = self.installed_apps.scan(state.serial)
        return AssistantOperation(
            result.ok,
            "Installed application scan complete" if result.ok else "Installed application scan failed",
            (
                f"{len(result.applications)} applications found for {result.serial}."
                if result.ok
                else "; ".join(result.errors)
            ),
            result,
        )

    def scan_runtime(self, state: AssistantState) -> AssistantOperation:
        result = self.target_discovery.discover_combined(state.serial)
        return AssistantOperation(
            result.ok,
            "Runtime target scan complete" if result.ok else "Runtime target scan failed",
            (
                f"{len(result.targets)} runtime targets found for {result.serial}."
                if result.ok
                else "; ".join(result.errors)
            ),
            result,
        )

    def check_tool(self, name: str) -> AssistantOperation:
        result = self.tool_diagnostics.check(name)
        return AssistantOperation(
            result.installed and not result.error,
            f"{result.display_name} is ready" if result.installed and not result.error else f"{result.display_name} is unavailable",
            result.version or result.error or result.executable_path or "",
            result,
        )

    def diagnose_frida(self, state: AssistantState) -> AssistantOperation:
        if not state.serial:
            return AssistantOperation(False, "No selected device", state.recommended_next_step)
        result = self.frida_manager.diagnose(state.serial)
        forwarding = (
            "27042 and 27043"
            if result.port_27042 and result.port_27043
            else "incomplete"
        )
        detail = (
            f"Reachable: {'yes' if result.reachable else 'no'} · "
            f"Server: {'running' if result.server_running else 'not detected'} · "
            f"Forwarding: {forwarding}"
        )
        if result.errors:
            detail += "\n" + "; ".join(result.errors)
        return AssistantOperation(result.reachable, "Frida route diagnosis", detail, result)

    def scripts(self) -> AssistantOperation:
        result = self.script_library.scan()
        descriptors = tuple(
            item for item in result.descriptors
            if getattr(getattr(item, "kind", None), "value", "") == "frida"
        )
        return AssistantOperation(
            result.ok,
            "Script Studio library scanned" if result.ok else "Script scan failed",
            f"{len(descriptors)} Frida scripts available." if result.ok else (result.error or ""),
            descriptors,
        )

    def _target(self, state: AssistantState):
        selected = self.selected_target_provider()
        if selected is not None:
            return selected
        if not state.target and not state.pid:
            return None
        target_type = TargetType.APPLICATION if state.target else TargetType.PROCESS
        return FridaTarget(
            state.target or f"PID {state.pid}",
            state.target or None,
            state.pid,
            target_type,
            bool(state.pid),
        )

    def frida_plan(
        self,
        state: AssistantState,
        *,
        mode="attach",
        trace=False,
        script_path="",
    ):
        return self.interactive_sessions.build_frida(
            state.serial,
            self._target(state),
            mode=mode,
            endpoint=state.endpoint,
            script_path=script_path,
            trace=trace,
        )

    def objection_plan(self, state: AssistantState, *, spawn=False):
        return self.interactive_sessions.build_objection(
            state.serial, state.target, spawn=spawn
        )

    def launch(self, plan) -> AssistantOperation:
        result = self.interactive_sessions.launch(plan)
        return AssistantOperation(
            result.ok,
            "External session launched" if result.ok else "Session launch failed",
            result.error or getattr(getattr(result, "record", None), "session_id", ""),
            result,
        )

    def objection_history(self) -> tuple[str, ...]:
        values = []
        for record in self.interactive_sessions.list():
            if getattr(record.session_type, "value", "") == "objection":
                values.extend(record.command_history)
        return tuple(values)

    @staticmethod
    def troubleshoot(kind: str, query: str) -> AssistantOperation:
        normalized = query.strip().casefold()
        entries = {
            "device is gone": "Check the same serial, application process, Frida endpoint, and SUS Companion-managed forwarding. A new attach or spawn may be required.",
            "target exited": "The selected process ended. Preserve the package and open a fresh confirmed attach or spawn plan.",
            "forwarding disappeared": "Inspect forwarding and repair only ports previously managed by SUS Companion.",
            "endpoint unavailable": "Verify ADB state, Frida Server or Gadget status, endpoint, and version compatibility.",
            "script destroyed": "Cleanup may report that an already-destroyed script cannot unload. Preserve the primary connection failure and start a fresh session if needed.",
        }
        matches = tuple(
            f"{title}: {detail}"
            for title, detail in entries.items()
            if not normalized or normalized in title or normalized in detail.casefold()
        )
        if kind == "objection":
            matches += (
                "Contextual help: `help android sslpinning` displays reference help; it is not the SSL-pinning action itself.",
            )
        return AssistantOperation(
            bool(matches),
            "Troubleshooting guidance",
            "\n\n".join(matches) if matches else "No local topic matched the search.",
            matches,
        )
