"""Real-widget smoke for Instrumentation Overview and validation feedback.

All collaborators are inert fakes.  The smoke never contacts a device or
launches ADB, Frida, Objection, a terminal, or another host process.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


SIZES = ((900, 650), (980, 650), (1180, 780), (1400, 860), (1920, 1028))
FRIDA_FIELDS = (
    "Server path:",
    "Server state:",
    "Server version:",
    "Host/server match:",
    "TCP 27042:",
    "TCP 27043:",
    "Reachability:",
)
FRIDA_ACTIONS = (
    "Diagnose Frida",
    "Start Server",
    "Stop Server",
    "Restart Server",
    "Repair Forwarding",
    "List Processes",
    "List Applications",
)


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def settle_tab_transition(root):
    root.after(120, root.quit)
    root.mainloop()
    root.update_idletasks()


def widget_with_text(parent, widget_type, text):
    return next(
        widget
        for widget in descendants(parent)
        if isinstance(widget, widget_type)
        and str(widget.cget("text")) == text
    )


def visible_in_viewport(widget, viewport):
    left = widget.winfo_rootx()
    top = widget.winfo_rooty()
    right = left + widget.winfo_width()
    bottom = top + widget.winfo_height()
    view_left = viewport.winfo_rootx()
    view_top = viewport.winfo_rooty()
    view_right = view_left + viewport.winfo_width()
    view_bottom = view_top + viewport.winfo_height()
    return (
        left >= view_left
        and top >= view_top
        and right <= view_right
        and bottom <= view_bottom
    )


class FakeFrida:
    def diagnose(self, _serial):
        raise AssertionError("The smoke must not diagnose a real device")

    def start_server(self, _serial):
        raise AssertionError("The smoke must not start a real server")

    def stop_server(self, _serial):
        raise AssertionError("The smoke must not stop a real server")

    def restart_server(self, _serial):
        raise AssertionError("The smoke must not restart a real server")

    def repair_forwarding(self, _serial):
        raise AssertionError("The smoke must not modify forwarding")

    def list_processes(self, _serial):
        raise AssertionError("The smoke must not list real processes")

    def list_applications(self, _serial):
        raise AssertionError("The smoke must not list real applications")


class FakeObjection:
    def __init__(self):
        self.next_readiness = SimpleNamespace(ready=True, errors=())
        self.readiness_calls = []
        self.launch_calls = []

    def readiness(self, serial, target, transport, **options):
        self.readiness_calls.append((serial, target, transport, options))
        return self.next_readiness

    def launch_external_session(self, command):
        self.launch_calls.append(tuple(command))
        raise AssertionError("Validation must not launch Objection")


class FakeInteractiveSessions:
    def __init__(self):
        self.build_calls = []
        self.launch_calls = []

    def build_objection(self, serial, target, **options):
        self.build_calls.append((serial, target, options))
        transport = options["transport"].casefold()
        return SimpleNamespace(
            ready=True,
            errors=(),
            descriptor=SimpleNamespace(
                device_serial=serial,
                target=target,
                transport=transport,
                network_host=options["host"],
                network_port=int(options["port"]),
            ),
        )

    def launch(self, plan):
        self.launch_calls.append(plan)
        raise AssertionError("Validation must not launch a session")


def main():
    import customtkinter as ctk

    from app.core.frida_manager import FridaDiagnosis
    from app.core.frida_target import FridaTarget, TargetType
    from app.gui.instrumentation_panel import InstrumentationPanel
    from app.gui.theme import get_theme

    root = ctk.CTk()
    root.minsize(1, 1)
    frida = FakeFrida()
    objection = FakeObjection()
    interactive = FakeInteractiveSessions()
    frida_statuses = []
    inert = SimpleNamespace()
    panel = InstrumentationPanel(
        root,
        get_theme(),
        inert,
        frida,
        objection,
        inert,
        inert,
        lambda _message: None,
        interactive_sessions=interactive,
        frida_status_callback=lambda serial, status, running: frida_statuses.append(
            (serial, status, running)
        ),
    )
    panel.pack(fill="both", expand=True)
    assert panel.overview_scroll.cget("border_width") == 0
    assert panel.overview_scroll.cget("fg_color") == "transparent"
    assert panel.overview_scroll._parent_frame.cget("border_width") == 0
    assert panel.target_sources.cget("border_width") == 0
    assert panel.target_sources.cget("fg_color") == "transparent"
    panel._show_frida_diagnosis(
        FridaDiagnosis(
            "fixture-serial",
            True,
            True,
            True,
            "/data/local/tmp/frida-server",
            "16.2.1",
            "16.2.1",
            True,
            True,
            True,
            True,
            recommendations=("Fixture readiness state.",),
        )
    )

    frida_section = panel.frida_labels["path"].master
    field_widgets = tuple(
        widget_with_text(frida_section, ctk.CTkLabel, text)
        for text in FRIDA_FIELDS
    )
    action_widgets = tuple(
        widget_with_text(frida_section, ctk.CTkButton, text)
        for text in FRIDA_ACTIONS
    )
    assert len(panel.frida_labels) == len(field_widgets) == 7
    assert tuple(label.cget("text") for label in panel.frida_labels.values()) == (
        "/data/local/tmp/frida-server",
        "Server running",
        "16.2.1",
        "Yes",
        "Yes",
        "Yes",
        "Yes",
    )
    assert tuple(widget.cget("text") for widget in action_widgets) == FRIDA_ACTIONS
    assert frida_statuses == [("fixture-serial", "Running", True)]

    geometry_results = []
    viewport = panel.overview_scroll._parent_canvas
    for width, height in SIZES:
        root.geometry(f"{width}x{height}+0+0")
        panel.internal_workspace.set("Overview")
        settle_tab_transition(root)
        assert root.winfo_width() == width and root.winfo_height() == height
        reachable = []
        for widget in (*field_widgets, *panel.frida_labels.values(), *action_widgets):
            panel.overview_scroll._scroll_router.ensure_visible(widget)
            root.update()
            assert widget.winfo_ismapped()
            assert visible_in_viewport(widget, viewport), (
                width, height, widget.cget("text"), viewport.yview()
            )
            reachable.append(str(widget.cget("text")))
        geometry_results.append(
            (width, height, len(reachable), tuple(round(value, 3) for value in viewport.yview()))
        )

    lifecycle_calls = []
    panel._lifecycle = lambda action, operation: lifecycle_calls.append(
        (action, operation)
    )
    start_button = action_widgets[FRIDA_ACTIONS.index("Start Server")]
    start_button.invoke()
    assert lifecycle_calls == [("Start", frida.start_server)]

    target = FridaTarget(
        "Fixture App", "org.example.fixture", 42, TargetType.APPLICATION, True
    )
    panel.device = SimpleNamespace(serial="fixture-serial", connected=True)
    panel.selected_target = target
    panel._update_target_actions()
    validate_button = widget_with_text(
        panel.sessions_tab, ctk.CTkButton, "Validate"
    )

    def run_synchronously(_title, operation, callback):
        callback(operation())

    panel._run_operation = run_synchronously
    panel.internal_workspace.set("Sessions")
    settle_tab_transition(root)
    assert panel.objection_session_guidance.winfo_ismapped()
    assert panel.objection_session_guidance.cget("text") == (
        "Attach requires the selected app/process to already be running. Open or "
        "otherwise start it on the device first. Spawn starts a non-running target."
    )
    validate_button.invoke()
    settle_tab_transition(root)
    assert panel.internal_workspace.get() == "Results"
    assert panel.results.winfo_ismapped()
    assert "Objection readiness checks passed." in panel.results.get("1.0", "end")

    objection.next_readiness = SimpleNamespace(
        ready=False,
        errors=("Frida is not reachable on the selected device.",),
    )
    panel.internal_workspace.set("Sessions")
    settle_tab_transition(root)
    validate_button.invoke()
    settle_tab_transition(root)
    assert panel.internal_workspace.get() == "Results"
    assert panel.results.winfo_ismapped()
    assert (
        "Frida is not reachable on the selected device."
        in panel.results.get("1.0", "end")
    )
    assert objection.readiness_calls == [
        (
            "fixture-serial", "org.example.fixture", "network",
            {"host": "127.0.0.1", "port": 27042},
        ),
        (
            "fixture-serial", "org.example.fixture", "network",
            {"host": "127.0.0.1", "port": 27042},
        ),
    ]
    assert not objection.launch_calls
    assert not interactive.launch_calls

    panel.destroy()
    root.destroy()
    print(
        "instrumentation-readiness-smoke=PASS "
        f"sizes={geometry_results} frida-fields=7 frida-actions=7 "
        "start-server-route=existing validation-success-failure=visible "
        "status-synchronized=1 objection-guidance=visible session-launches=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
