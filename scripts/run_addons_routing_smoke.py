#!/usr/bin/env python3
"""Exercise Add-ons menu destinations through the real application shell."""

from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextmanager
def isolated_environment(temporary_root):
    working_directory = Path(temporary_root) / "application working directory"
    configuration_directory = Path(temporary_root) / "configuration"
    working_directory.mkdir(parents=True)
    configuration_directory.mkdir(parents=True)
    original_working_directory = Path.cwd()
    original_xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    try:
        os.environ["XDG_CONFIG_HOME"] = str(configuration_directory)
        os.chdir(working_directory)
        yield
    finally:
        os.chdir(original_working_directory)
        if original_xdg_config_home is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = original_xdg_config_home


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def visible_text(widget):
    return {
        str(item.cget("text"))
        for item in descendants(widget)
        if "text" in getattr(item, "keys", lambda: ())()
        and item.winfo_ismapped()
    }


def main():
    with tempfile.TemporaryDirectory() as directory, isolated_environment(directory):
        from app.gui.main_window import SusADBWindow

        app = SusADBWindow()
        app._deferred_started = True
        app.update()
        top = app.nametowidget(app.cget("menu"))
        cascades = [
            index for index in range(top.index("end") + 1)
            if top.type(index) == "cascade"
        ]
        labels = [top.entrycget(index, "label") for index in cascades]
        addons = top.nametowidget(
            top.entrycget(cascades[labels.index("Add-ons")], "menu")
        )
        command_labels = [
            addons.entrycget(index, "label")
            for index in range(addons.index("end") + 1)
            if addons.type(index) == "command"
        ]
        assert command_labels[:4] == [
            "Open Add-ons Center…",
            "Official Add-on Catalog…",
            "Manage Installed Add-ons…",
            "Add-on Diagnostics…",
        ]

        results = []
        for width, height in ((1100, 700), (1200, 760), (1400, 860)):
            app.geometry(f"{width}x{height}+0+0")
            app.update()

            addons.invoke(0)
            app.update()
            center = app.addons_center
            assert center is not None and center.winfo_exists()
            assert center.title().endswith("— Add-ons Center")
            assert "⚙ ADD-ONS CENTER ⚙" in visible_text(center)
            assert len(center.cards) == 7

            addons.invoke(1)
            app.update()
            plugin_panel = app.pentest_workspace.plugin_panel
            assert app.workspace.get() == "Pentest"
            assert app.pentest_workspace.workspace.get() == "Plugins"
            assert plugin_panel.tabs.get() == "Official Catalog"
            assert len(plugin_panel.official_cards.winfo_children()) == 7
            assert app.addons_center is center and center.winfo_exists()
            assert "⚙ ADD-ONS CENTER ⚙" in visible_text(center)

            plugin_panel.tabs.set("Installed")
            addons.invoke(1)
            app.update()
            assert app.pentest_workspace.plugin_panel is plugin_panel
            assert plugin_panel.tabs.get() == "Official Catalog"
            assert app.addons_center is center

            addons.invoke(0)
            app.update()
            assert app.addons_center is center
            assert app.pentest_workspace.plugin_panel is plugin_panel
            assert plugin_panel.tabs.get() == "Official Catalog"

            addons.invoke(2)
            app.update()
            assert app.pentest_workspace.plugin_panel is plugin_panel
            assert plugin_panel.tabs.get() == "Installed"
            assert app.addons_center is center

            addons.invoke(3)
            app.update()
            assert app.pentest_workspace.plugin_panel is plugin_panel
            assert plugin_panel.tabs.get() == "Diagnostics"
            assert app.addons_center is center
            results.append((width, height, len(center.cards)))

        app.shutdown()
    print(
        "addons-routing-smoke=PASS "
        f"sizes={results} center-instance=stable catalog-instance=stable "
        "coexistence=PASS distinct-content=PASS installed=PASS diagnostics=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
