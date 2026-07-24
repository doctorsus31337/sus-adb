"""Headless compact-window smoke for local help and deterministic guidance."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _inside(window, widget):
    return (
        widget.winfo_rootx() >= window.winfo_rootx()
        and widget.winfo_rooty() >= window.winfo_rooty()
        and widget.winfo_rootx() + widget.winfo_width()
        <= window.winfo_rootx() + window.winfo_width() + 2
        and widget.winfo_rooty() + widget.winfo_height()
        <= window.winfo_rooty() + window.winfo_height() + 2
    )


def main():
    import customtkinter as ctk

    from app.core.context_help import HelpRegistry
    from app.core.guide_engine import GuideEngine, GuideState
    from app.gui.context_help_window import ContextHelpWindow
    from app.gui.guided_setup_window import GuidedSetupWindow
    from app.gui.theme import get_theme

    root = ctk.CTk()
    root.withdraw()
    theme = get_theme()
    help_window = ContextHelpWindow(
        root, theme, HelpRegistry(),
        interface_mode_provider=lambda: "guided",
    )
    guide = GuidedSetupWindow(
        root, theme, GuideEngine(),
        lambda: GuideState(selected_serial="FIXTURE", adb_state="device"),
    )
    for width, height in ((900, 650), (980, 650), (1180, 780), (1400, 860)):
        for window in (help_window, guide):
            window.geometry(f"{width}x{height}+0+0")
            window.update_idletasks()
            assert window.winfo_width() == width
            assert window.winfo_height() == height
            assert all(_inside(window, child) for child in window.winfo_children())
    help_window.show_topic("sessions-center")
    assert "Automatic" not in help_window.topic_text.get("1.0", "end")
    help_window.tabs.set("Glossary")
    help_window.search.insert(0, "temporary numeric")
    help_window._search_changed()
    assert "PID" in help_window.glossary_text.get("1.0", "end")
    for _ in range(10):
        guide.next()
    assert guide.step == len(guide.STEPS) - 1
    assert guide.open_button.cget("state") == "normal"
    assert not guide.plan.executes_automatically
    assert all(
        not value.casefold().startswith("blue")
        for value in theme.values() if isinstance(value, str)
    )
    help_window.close()
    guide.close()
    root.destroy()
    print(
        "guided-help-smoke=PASS "
        "sizes=900x650,980x650,1180x780,1400x860 "
        "glossary=PASS deterministic-guide=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
