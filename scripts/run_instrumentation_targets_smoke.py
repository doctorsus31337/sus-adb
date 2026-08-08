"""Focused headless layout smoke for Instrumentation -> Targets.

The smoke uses inert collaborators and never contacts a device or launches a
tool.  Pass ``--screenshot-dir`` to capture both target-source tabs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


SIZES = ((900, 650), (980, 650), (1180, 780), (1400, 860))


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def fully_visible(widget, container):
    return (
        widget.winfo_rootx() >= container.winfo_rootx()
        and widget.winfo_rooty() >= container.winfo_rooty()
        and widget.winfo_rootx() + widget.winfo_width()
        <= container.winfo_rootx() + container.winfo_width()
        and widget.winfo_rooty() + widget.winfo_height()
        <= container.winfo_rooty() + container.winfo_height()
    )


def button_text_fits(widget):
    text = str(widget.cget("text"))
    font = getattr(widget, "_font", None)
    if not text or font is None or not hasattr(font, "measure"):
        return True
    return max(font.measure(line) for line in text.splitlines()) + 18 <= widget.winfo_width()


def inside_segmented_button(widget):
    import customtkinter as ctk

    ancestor = getattr(widget, "master", None)
    while ancestor is not None:
        if isinstance(ancestor, ctk.CTkSegmentedButton):
            return True
        ancestor = getattr(ancestor, "master", None)
    return False


def button(parent, text):
    import customtkinter as ctk

    return next(
        widget
        for widget in descendants(parent)
        if isinstance(widget, ctk.CTkButton) and widget.cget("text") == text
    )


def mapped_controls(parent):
    import customtkinter as ctk

    control_types = (
        ctk.CTkButton,
        ctk.CTkCheckBox,
        ctk.CTkEntry,
        ctk.CTkSegmentedButton,
    )
    return tuple(
        widget
        for widget in descendants(parent)
        if isinstance(widget, control_types) and widget.winfo_ismapped()
    )


def capture(root, destination, source, width, height):
    if destination is None:
        return
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"after-{source}-{width}x{height}.png"
    subprocess.run(
        [
            "import", "-window", "root", "-crop",
            f"{width}x{height}+0+0", str(path),
        ],
        check=True,
    )


def settle_tab_transition(root):
    root.after(120, root.quit)
    root.mainloop()
    root.update_idletasks()


class RecordingSessions:
    def __init__(self):
        self.calls = []

    def build_frida(self, serial, target, **options):
        self.calls.append(("frida", serial, target, options))
        return SimpleNamespace(ready=False, errors=())

    def build_objection(self, serial, target, **options):
        self.calls.append(("objection", serial, target, options))
        return SimpleNamespace(ready=False, errors=())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot-dir", type=Path)
    arguments = parser.parse_args()

    import customtkinter as ctk

    from app.core.frida_target import FridaTarget, TargetType
    from app.gui.instrumentation_panel import InstrumentationPanel
    from app.gui.theme import get_theme

    root = ctk.CTk()
    root.minsize(1, 1)
    root.geometry("900x650+0+0")
    sessions = RecordingSessions()
    inert = SimpleNamespace()
    panel = InstrumentationPanel(
        root,
        get_theme(),
        inert,
        inert,
        inert,
        inert,
        inert,
        lambda _message: None,
        interactive_sessions=sessions,
    )
    panel.pack(fill="both", expand=True)
    panel.internal_workspace.set("Targets")

    assert panel.internal_workspace.cget("border_width") == 1
    assert panel.target_sources.cget("border_width") == 0
    assert panel.target_sources.cget("fg_color") == "transparent"
    for workspace in (
        panel.installed_targets_workspace,
        panel.runtime_targets_workspace,
    ):
        assert workspace.cget("border_width") == 0
        assert workspace.cget("fg_color") == "transparent"
    for actions in (
        panel.installed_targets_actions,
        panel.runtime_targets_actions,
    ):
        assert actions.cget("border_width") == 0
        assert actions.cget("fg_color") == panel.theme["panel_alt"]
    for viewport in (panel.installed_list, panel.target_list):
        assert viewport.cget("border_width") == 0
        assert viewport._parent_frame.cget("border_width") == 0
        assert viewport._scroll_router.keyboard

    panel.target_sources.set("Installed Applications")
    settle_tab_transition(root)
    installed_text = {
        str(widget.cget("text"))
        for widget in descendants(panel.targets_tab)
        if "text" in getattr(widget, "keys", lambda: ())()
    }
    assert {
        "Installed Applications — ADB-backed (Frida not required)",
        "Scan Installed Apps",
        "Guided Instrumentation Setup",
        "Help",
        "Launchable only",
        "Running only",
        "Scan not run",
    } <= installed_text
    assert panel.installed_search._entry.bind("<KeyRelease>")
    assert callable(panel.scan_installed_button._command)
    assert callable(button(panel.targets_tab, "Guided Instrumentation Setup")._command)
    assert callable(button(panel.targets_tab, "Help")._command)

    panel.target_sources.set("Runtime Targets")
    settle_tab_transition(root)
    runtime_text = {
        str(widget.cget("text"))
        for widget in descendants(panel.targets_tab)
        if "text" in getattr(widget, "keys", lambda: ())()
    }
    assert {
        "Runtime Targets — Frida-backed",
        "Scan Running Processes",
        "Clear Search",
        "Copy Version Guidance",
        "Name:",
        "Identifier:",
        "PID:",
        "Type:",
        "Running:",
        "0 targets",
    } <= runtime_text
    assert panel.search_entry._entry.bind("<KeyRelease>")
    assert callable(panel.refresh_targets_button._command)
    assert callable(button(panel.targets_tab, "Clear Search")._command)

    target = FridaTarget(
        "Fixture App", "org.example.fixture", 42, TargetType.APPLICATION, True
    )
    panel.device = SimpleNamespace(serial="fixture-serial")
    panel.selected_target = target
    panel.trace_pattern.insert(0, "open*")
    panel._build_frida_plan("attach")
    panel._build_frida_plan("trace")
    panel._build_objection_plan(False)
    assert sessions.calls == [
        (
            "frida", "fixture-serial", target,
            {"mode": "attach", "trace": False, "trace_pattern": "open*"},
        ),
        (
            "frida", "fixture-serial", target,
            {"mode": "attach", "trace": True, "trace_pattern": "open*"},
        ),
        (
            "objection", "fixture-serial", "org.example.fixture",
            {
                "spawn": False,
                "transport": "Network",
                "host": "127.0.0.1",
                "port": "27042",
            },
        ),
    ]
    routed = []
    panel.launch_frida = lambda mode: routed.append(("frida", mode))
    panel.launch_objection = lambda spawn: routed.append(("objection", spawn))
    panel.frida_attach_button._command()
    panel.frida_trace_button._command()
    panel.objection_attach_button._command()
    panel.objection_spawn_button._command()
    assert routed == [
        ("frida", "attach"),
        ("frida", "trace"),
        ("objection", False),
        ("objection", True),
    ]

    geometry_results = []
    for width, height in SIZES:
        root.geometry(f"{width}x{height}+0+0")
        panel.target_sources.set("Installed Applications")
        settle_tab_transition(root)
        assert root.winfo_width() == width and root.winfo_height() == height
        controls = mapped_controls(panel.targets_tab)
        outside = [
            (
                widget.__class__.__name__,
                str(widget.cget("text")) if "text" in widget.keys() else "",
                widget.winfo_rootx(), widget.winfo_rooty(),
                widget.winfo_width(), widget.winfo_height(),
            )
            for widget in controls
            if not fully_visible(widget, panel)
        ]
        assert controls and not outside, (width, height, outside)
        clipped_labels = [
            (widget.cget("text"), widget.winfo_width())
            for widget in controls
            if isinstance(widget, ctk.CTkButton)
            and not inside_segmented_button(widget)
            and not button_text_fits(widget)
        ]
        assert not clipped_labels, clipped_labels
        capture(root, arguments.screenshot_dir, "installed", width, height)

        panel.target_sources.set("Runtime Targets")
        settle_tab_transition(root)
        controls = mapped_controls(panel.targets_tab)
        outside = [
            (
                widget.__class__.__name__,
                str(widget.cget("text")) if "text" in widget.keys() else "",
                widget.winfo_rootx(), widget.winfo_rooty(),
                widget.winfo_width(), widget.winfo_height(),
            )
            for widget in controls
            if not fully_visible(widget, panel)
        ]
        assert controls and not outside, (width, height, outside)
        clipped_labels = [
            (widget.cget("text"), widget.winfo_width())
            for widget in controls
            if isinstance(widget, ctk.CTkButton)
            and not inside_segmented_button(widget)
            and not button_text_fits(widget)
        ]
        assert not clipped_labels, clipped_labels
        capture(root, arguments.screenshot_dir, "runtime", width, height)
        geometry_results.append((width, height, len(controls)))

    panel.destroy()
    root.destroy()
    print(
        "instrumentation-targets-smoke=PASS "
        f"sizes={geometry_results} controls=present routes=unchanged "
        "primary-borders=1 internal-borders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
