#!/usr/bin/env python3
"""Isolated local-only acceptance smoke for the Universal Command Palette."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import customtkinter as ctk

from app.core.command_palette import PaletteCommand
from app.core.host_state import DeviceState, HostStateSnapshot
from app.gui.main_window import SusADBWindow
from app.plugins.contribution_registry import Contribution


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def menu_named(root, label):
    menu = root.nametowidget(root.cget("menu"))
    for index in range(menu.index("end") + 1):
        if menu.type(index) == "cascade" and menu.entrycget(index, "label") == label:
            return menu.nametowidget(menu.entrycget(index, "menu"))
    raise AssertionError(f"Missing menu: {label}")


def query(palette, value):
    palette.search.delete(0, "end")
    palette.search.insert(0, value)
    palette.refresh()
    return tuple(match.command for match in palette.matches)


def geometry_measurement(palette, width, height):
    palette.geometry(f"{width}x{height}+0+0")
    palette.update_idletasks()
    search = palette.search
    viewport = palette.result_area.canvas
    footer = palette.footer
    final = palette.result_buttons[-1]
    palette.select_index(len(palette.matches) - 1)
    palette.update_idletasks()
    assert palette.winfo_width() == width and palette.winfo_height() == height
    assert search.winfo_rootx() >= palette.winfo_rootx()
    assert search.winfo_rootx() + search.winfo_width() <= palette.winfo_rootx() + width
    assert viewport.winfo_rooty() + viewport.winfo_height() <= footer.winfo_rooty()
    assert final.winfo_rooty() + final.winfo_height() <= footer.winfo_rooty()
    assert palette.winfo_rootx() >= 0 and palette.winfo_rooty() >= 0
    return (
        f"{width}x{height}",
        (search.winfo_rootx(), search.winfo_rooty(), search.winfo_width(), search.winfo_height()),
        (viewport.winfo_rootx(), viewport.winfo_rooty(), viewport.winfo_width(), viewport.winfo_height()),
        (final.winfo_rootx(), final.winfo_rooty(), final.winfo_width(), final.winfo_height()),
        footer.winfo_rooty(),
        palette.result_area.scrollbar.winfo_width(),
    )


def main():
    SusADBWindow.startup_check = lambda self: None
    app = SusADBWindow()
    app.geometry("1200x760+0+0")
    app.update_idletasks()
    assert app.command_palette is None
    assert app.command_palette_registry is None
    assert all(host.panel is None for host in app.workspace_hosts.values())
    assert not app.plugin_manager._refreshed

    app.focus_force()
    app.event_generate("<Control-k>")
    app.update()
    palette = app.command_palette
    assert palette is not None and palette.winfo_exists()
    assert not app.plugin_manager._refreshed
    assert app.open_command_palette() is palette
    assert palette.focus_search() is palette
    assert app.host_state.subscription_count("command-palette") == 1

    view = menu_named(app, "View")
    command_index = next(
        index for index in range(view.index("end") + 1)
        if view.type(index) == "command"
        and view.entrycget(index, "label") == "Command Palette"
    )
    view.invoke(command_index)
    assert app.command_palette is palette

    empty = query(palette, "")
    assert empty and empty[0].title == "Workspace Home"
    assert len(empty) <= palette.RESULT_LIMIT
    assert query(palette, "Console")[0].title == "Console"
    assert query(palette, "adb shell")[0].title == "Sessions Center"
    frida = {item.title for item in query(palette, "frida")}
    assert {"Frida Assistant", "Instrumentation"} <= frida
    assert query(palette, "objection")[0].title == "Objection Assistant"
    assert query(palette, "recovery")[0].title == "Device Rescue & Recovery"

    query(palette, "")
    palette.select_index(0)
    palette.move_selection(1)
    assert palette.selected_index == 1
    palette.move_selection(palette.PAGE_SIZE)
    assert palette.selected_index == 7
    palette.select_index(len(palette.matches) - 1)
    assert palette.selected_index == len(palette.matches) - 1
    palette.select_index(0)
    assert palette.selected_index == 0
    before = palette.result_area.canvas.yview()
    palette.result_area._wheel(
        SimpleNamespace(widget=palette.result_buttons[-1], num=5, delta=-120)
    )
    assert palette.result_area.canvas.yview() != before

    measurements = [
        geometry_measurement(palette, width, height)
        for width, height in ((720, 500), (820, 560), (960, 640), (1180, 720))
    ]
    for scale in (1.25, 1.5):
        ctk.set_widget_scaling(scale)
        palette.geometry("820x560+0+0")
        palette.update_idletasks()
        assert palette.search.winfo_width() > 500
        assert palette.result_area.scrollbar.winfo_width() >= 17
    ctk.set_widget_scaling(1.0)

    app.set_interface_mode("advanced")
    app.after(30, app.quit)
    app.mainloop()
    assert app.command_palette is palette
    assert palette.mode_label.cget("text") == "Advanced mode"
    app.host_state.publish(
        HostStateSnapshot(
            selected_device=DeviceState(
                "fixture-serial", "Fixture", state="device",
                display_name="Fixture Device",
            ),
            interface_mode="advanced",
        )
    )
    app.after(30, app.quit)
    app.mainloop()
    query(palette, "Instrumentation")
    assert "fixture-serial" in palette.matches[0].command.technical_context
    assert app.command_palette is palette

    palette.close()
    assert app.command_palette is None
    assert app.host_state.subscription_count("command-palette") == 0
    palette = app.open_command_palette()
    assert app.host_state.subscription_count("command-palette") == 1
    palette.close()
    assert app.host_state.subscription_count("command-palette") == 0

    app.navigate_workspace("Home")
    palette = app.open_command_palette()
    query(palette, "Console")
    palette.result_buttons[0].invoke()
    app.update_idletasks()
    assert app.workspace.get() == "Console"
    assert app.workspace_controller.current == "Console"

    palette = app.open_command_palette()
    query(palette, "adb shell")
    palette.activate_selected()
    app.update_idletasks()
    sessions = app.sessions_center
    assert sessions is app.open_sessions_center()
    assert not app.interactive_sessions.list()
    sessions.focus_force()
    app.update()
    sessions.event_generate("<Control-k>")
    app.update()
    assert app.command_palette is not None
    app.command_palette.close()
    sessions.close()

    palette = app.open_command_palette()
    help_results = query(palette, "PID")
    help_index = next(
        index for index, item in enumerate(help_results)
        if item.command_id == "tool.context-help"
    )
    palette.select_index(help_index)
    palette.activate_selected()
    app.update_idletasks()
    assert app.context_help_window.search.get() == "PID"
    app.context_help_window.close()

    routed = []
    opened = []
    original_addons = app.open_addons_center
    original_open = app.open_addon_window
    app.open_addons_center = lambda value=None: routed.append(value)
    app.open_addon_window = lambda value: opened.append(value)
    available = next(
        item for item in app._command_palette_commands()
        if item.command_id == "addon.frida-assistant"
    )
    available.invoke("")
    assert routed[-1] == "Frida Assistant"
    assert not app.plugin_manager.records
    manifest = SimpleNamespace(
        plugin_id="fixture.palette-addon",
        name="Fixture Palette Addon",
    )
    app.plugin_manager.records[manifest.plugin_id] = (
        Path("/tmp/fixture"),
        SimpleNamespace(package_digest="fixture-digest"),
        manifest,
    )
    app.plugin_registry.register(
        manifest.plugin_id,
        (
            Contribution(
                "fixture.palette-panel", "pentest-panel",
                "Fixture Palette Panel", manifest.plugin_id,
            ),
        ),
    )
    with patch("app.plugins.addon_presenter.lifecycle_for", return_value="Loaded"):
        catalog = app._command_palette_commands()
    addon = next(item for item in catalog if item.command_id.startswith("addon.installed."))
    addon.invoke("")
    assert opened == ["fixture.palette-panel"]
    with patch("app.plugins.addon_presenter.lifecycle_for", return_value="Installed"):
        catalog = app._command_palette_commands()
    addon = next(item for item in catalog if item.command_id.startswith("addon.installed."))
    addon.invoke("")
    assert routed[-1] == "Fixture Palette Addon"
    assert "Requires Enable" == addon.unavailable_reason
    app.plugin_registry.unregister_plugin(manifest.plugin_id)
    app.plugin_manager.records.pop(manifest.plugin_id)
    app.open_addons_center = original_addons
    app.open_addon_window = original_open

    called = []
    original_provider = app._command_palette_commands
    app._command_palette_commands = lambda: (
        PaletteCommand(
            "blocked", "Unavailable Result", "Cannot run", "Tools",
            available=False, unavailable_reason="Missing optional tool",
            invoke=lambda _query: called.append(True),
        ),
    )
    palette = app.open_command_palette()
    palette.activate_selected()
    assert not called and palette.winfo_exists()
    palette.close()
    app._command_palette_commands = original_provider

    assert app._command_palette_shortcut(SimpleNamespace(widget=".native.dialog")) is None
    assert all(
        not value.casefold().startswith("blue")
        for value in app.theme.values() if isinstance(value, str)
    )
    assert not any(worker.is_alive() for worker in app._background_workers)
    app.shutdown()
    print(
        "command-palette-smoke=PASS "
        f"measurements={measurements} "
        "main=1200x760 palette=720x500,820x560,960x640,1180x720 "
        "scaling=125%,150% keyboard=PASS wheel=PASS addon-routing=PASS "
        "native-dialog-guard=PASS lazy=PASS shutdown=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
