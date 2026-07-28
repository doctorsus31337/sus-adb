#!/usr/bin/env python3
"""Local-only GUI acceptance smoke for the Workflow Recipes center."""

from __future__ import annotations

import customtkinter as ctk

from app.core.workflow_recipes import (
    RecipeRunController,
    RecipeRunStatus,
    RecipeSpec,
    RecipeStepResult,
    RecipeStepSpec,
    StepActionClass,
)
from app.gui.main_window import SusADBWindow
from app.gui.customtkinter_compat import focused_within
from app.gui.workflow_recipes_window import WorkflowRecipesWindow


def menu_named(root, label):
    menu = root.nametowidget(root.cget("menu"))
    for index in range(menu.index("end") + 1):
        if menu.type(index) == "cascade" and menu.entrycget(index, "label") == label:
            return menu.nametowidget(menu.entrycget(index, "menu"))
    raise AssertionError(f"Missing menu: {label}")


def button_text_fits(button):
    font = getattr(button, "_font", None)
    return (
        font is None
        or max(font.measure(line) for line in str(button.cget("text")).splitlines())
        + 18
        <= button.winfo_width()
    )


def click(widget):
    """Generate a real CustomTkinter surface click."""
    surface = getattr(widget, "_label", None) or getattr(widget, "_canvas", widget)
    surface.event_generate("<Button-1>", x=3, y=3)


def specifications(calls):
    values = []
    attempts = {}
    def check(state, value):
        attempts[value] = attempts.get(value, 0) + 1
        calls.append((value, state.selected_serial, "check"))
        return RecipeStepResult(
            attempts[value] > 1,
            (
                "Synthetic local check complete."
                if attempts[value] > 1 else
                "Synthetic local check failed."
            ),
            next_guidance="Choose Continue explicitly.",
        )
    for index in range(12):
        steps = (
            RecipeStepSpec(
                f"explain-{index}",
                "Review the intended procedure",
                "Starting a recipe does not run this informational step.",
                "Keep progression operator-owned.",
                StepActionClass.INFORMATIONAL,
            ),
            RecipeStepSpec(
                f"optional-{index}",
                "Review an optional note",
                "This optional manual step may be skipped explicitly.",
                "Prove optional progressive disclosure.",
                StepActionClass.MANUAL,
                optional=True,
            ),
            RecipeStepSpec(
                f"check-{index}",
                "Run a bounded local check",
                "Invoke exactly one injected callback.",
                "Prove explicit one-step execution.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=lambda state, value=index: check(state, value),
            ),
            RecipeStepSpec(
                f"review-{index}",
                "Review one state-changing action",
                "This synthetic callback retains explicit confirmation.",
                "Prove the existing confirmation semantics are unchanged.",
                StepActionClass.STATE_CHANGING,
                action_label="Review Action",
                invoke=lambda state, value=index: (
                    calls.append((value, state.selected_serial, "review"))
                    or RecipeStepResult(True, "Synthetic review complete.")
                ),
            ),
        )
        values.append(
            RecipeSpec(
                f"fixture-{index}",
                (
                    "Fixture Recipe 1 With An Exceptionally Long Operator Review Title"
                    if index == 0 else
                    f"Fixture Recipe {index + 1}"
                ),
                "A synthetic local-only recipe with no backend operations.",
                "Fixture",
                "Low",
                ("Explicit review",),
                steps,
                ("fixture", "checklist"),
            )
        )
    return tuple(values)


def main():
    SusADBWindow.startup_check = lambda self: None
    app = SusADBWindow()
    app.geometry("1200x760+0+0")
    app.update_idletasks()
    assert app.workflow_recipes_window is None
    assert app.workflow_recipe_controller is None
    assert all(host.panel is None for host in app.workspace_hosts.values())

    tools = menu_named(app, "Tools")
    index = next(
        item for item in range(tools.index("end") + 1)
        if tools.type(item) == "command"
        and tools.entrycget(item, "label") == "Workflow Recipes"
    )
    tools.invoke(index)
    window = app.workflow_recipes_window
    assert window is app.open_workflow_recipes()
    window.confirm_callback = lambda _title, _message: True
    app.update()
    assert app.host_state.subscription_count("workflow-recipes") == 1
    assert not app.plugin_manager._refreshed
    assert len(window.controller.recipes) == 5
    card = window.recipe_cards["device-readiness"]
    for part in ("card", "title", "description", "metadata"):
        window._selected_recipe_id = ""
        click(card[part])
        app.update()
        assert window._selected_recipe_id == "device-readiness"
        assert window.controller.state.recipe_id == ""
    assert card["card"].cget("border_color") == app.theme["gold"]
    assert card["review"].cget("text") == "Review"
    card["review"].invoke()
    app.update()
    assert window._view == "overview"
    assert window.controller.state.recipe_id == ""
    assert "Starting this recipe does not run a step." == (
        window.overview_widgets["notice"].cget("text")
    )
    assert "Informational" in window.overview_widgets["outline"].cget("text")
    assert window.footer_buttons["primary"].cget("text") == "Start Device Readiness"
    window.footer_buttons["primary"].invoke()
    app.update()
    accepted_controller = window.controller
    assert accepted_controller.state.recipe_id == "device-readiness"
    assert accepted_controller.state.current_step_index == 0
    assert all(value is None for value in accepted_controller.state.step_results)
    window.footer_buttons["primary"].invoke()
    app.update()
    accepted_progress = accepted_controller.state.step_statuses
    window.show_library()
    assert accepted_controller.state.recipe_id == "device-readiness"
    assert "Active recipe: Device Readiness" in window.state_label.cget("text")
    window.select_recipe("frida-readiness")
    window.show_overview()
    assert accepted_controller.state.recipe_id == "device-readiness"
    warning = window.overview_widgets["active_warning"].cget("text")
    assert "Active recipe: Device Readiness" in warning
    assert "review Frida Readiness" in warning
    assert "Only one recipe can be active at a time." in warning
    assert window.footer_buttons["primary"].cget("text") == "Resume Device Readiness"
    assert window.footer_buttons["cancel"].cget("text") == "Cancel Device Readiness"
    window.footer_buttons["primary"].invoke()
    assert window._view == "active"
    assert accepted_controller.state.recipe_id == "device-readiness"
    assert accepted_controller.state.step_statuses == accepted_progress
    window._escape()
    assert window._view == "overview"
    window._escape()
    assert window._view == "library"
    window.select_recipe("frida-readiness")
    window.show_overview()
    window.footer_buttons["cancel"].invoke()
    app.update()
    assert window._view == "overview"
    assert window._selected_recipe_id == "frida-readiness"
    assert accepted_controller.state.recipe_id == "device-readiness"
    assert accepted_controller.state.status is RecipeRunStatus.CANCELLED
    assert window.footer_buttons["primary"].cget("text") == "Start Frida Readiness"
    window.footer_buttons["primary"].invoke()
    app.update()
    assert accepted_controller.state.recipe_id == "frida-readiness"
    assert accepted_controller.state.current_step_index == 0
    assert all(value is None for value in accepted_controller.state.step_results)
    window.close()
    assert app.workflow_recipes_window is None
    assert app.host_state.subscription_count("workflow-recipes") == 0
    recipe_command = next(
        command for command in app._command_palette_commands()
        if command.command_id == "recipe.broken-screen-recovery"
    )
    recipe_command.invoke("")
    focused = app.workflow_recipes_window
    assert focused.search.get() == "Broken-Screen Recovery Preparation"
    assert focused._selected_recipe_id == "broken-screen-recovery"
    assert focused.controller.state.recipe_id == "frida-readiness"
    assert focused.controller.state.current_step_index == 0
    focused.close()
    reopened = app.open_workflow_recipes()
    assert reopened.controller.state.recipe_id == "frida-readiness"
    assert reopened.controller.state.current_step_index == 0
    reopened.close()

    calls = []
    controller = RecipeRunController(specifications(calls))
    window = WorkflowRecipesWindow(
        app,
        app.theme,
        controller,
        app.host_state,
        mode_provider=lambda: app.interface_mode,
        confirm_callback=lambda _title, _message: True,
    )
    app.update()
    assert len(window.library.winfo_children()) == 12
    assert not calls
    window.focus_recipe("fixture-11")
    assert "Fixture Recipe 12" == window.search.get()
    assert window._selected_recipe_id == "fixture-11"
    assert controller.state.recipe_id == ""
    window.search.delete(0, "end")
    window.render_library()
    assert window._selected_recipe_id == "fixture-11"
    window.search.insert(0, "Fixture Recipe 2")
    window.render_library()
    assert window._selected_recipe_id == ""
    window.search.delete(0, "end")
    window.render_library()
    app.update()
    parts = window.recipe_cards["fixture-0"]
    click(parts["title"])
    app.update()
    assert window._selected_recipe_id == "fixture-0"
    click(parts["description"])
    app.update()
    assert window._selected_recipe_id == "fixture-0"
    parts["focus"].focus_set()
    parts["focus"].event_generate("<Return>")
    app.update()
    assert window._view == "overview"
    assert controller.state.recipe_id == ""
    assert not calls
    outline = window.overview_widgets["outline"].cget("text")
    assert all(
        value in outline
        for value in ("Informational", "Manual", "Read Only", "State Changing")
    )
    window.footer_buttons["primary"].invoke()
    app.update()
    assert not calls
    assert controller.state.current_step_index == 0
    assert window.footer_buttons["primary"].cget("text") == "Mark Complete"
    assert "skip" not in window.footer_buttons
    assert "previous" not in window.footer_buttons
    assert len(
        tuple(
            button for button in window.footer_buttons.values()
            if button.cget("fg_color") == app.theme["red"]
        )
    ) == 1
    window.footer_buttons["primary"].focus_force()
    app.update()
    assert focused_within(window.footer_buttons["primary"])
    window.footer_buttons["primary"].invoke()
    app.update()
    assert window.footer_buttons["primary"].cget("text") == "Continue"
    assert focused_within(window.footer_buttons["primary"])
    window.footer_buttons["primary"].invoke()
    app.update()
    assert controller.state.current_step_index == 1 and not calls
    assert window.footer_buttons["primary"].cget("text") == "Mark Complete"
    assert "skip" in window.footer_buttons
    assert "previous" in window.footer_buttons
    window.footer_buttons["skip"].invoke()
    app.update()
    assert window.footer_buttons["primary"].cget("text") == "Continue"
    assert "skip" not in window.footer_buttons
    window.footer_buttons["primary"].invoke()
    app.update()
    assert controller.state.current_step_index == 2
    assert window.footer_buttons["primary"].cget("text") == "Run Check"
    assert "skip" not in window.footer_buttons
    window.footer_buttons["primary"].invoke()
    app.update()
    assert calls == [(0, "", "check")]
    assert window.footer_buttons["primary"].cget("text") == "Retry"
    window.footer_buttons["primary"].invoke()
    app.update()
    assert calls == [(0, "", "check"), (0, "", "check")]
    assert window.footer_buttons["primary"].cget("text") == "Continue"
    window.footer_buttons["primary"].invoke()
    app.update()
    assert controller.state.current_step_index == 3
    assert window.footer_buttons["primary"].cget("text") == "Review Action"
    window.footer_buttons["primary"].invoke()
    app.update()
    assert calls[-1] == (0, "", "review")
    assert window.footer_buttons["primary"].cget("text") == "Continue"

    measurements = []
    for width, height in ((900, 650), (980, 650), (1180, 780), (1400, 860)):
        window.geometry(f"{width}x{height}+0+0")
        window.update_idletasks()
        assert window.winfo_width() == width and window.winfo_height() == height
        assert window.search.winfo_rootx() >= window.winfo_rootx()
        assert (
            window.body.winfo_rooty() + window.body.winfo_height()
            <= window.footer.winfo_rooty()
        )
        assert (
            window.footer.winfo_rooty() + window.footer.winfo_height()
            <= window.winfo_rooty() + window.winfo_height()
        )
        assert all(button_text_fits(button) for button in window.footer_buttons.values())
        assert len(
            tuple(
                button for button in window.footer_buttons.values()
                if button.cget("fg_color") == app.theme["red"]
            )
        ) == 1
        assert all(
            button.cget("fg_color") == app.theme["panel_alt"]
            for role, button in window.footer_buttons.items()
            if role != "primary"
        )
        measurements.append(
            (
                f"{width}x{height}",
                (
                    window.search.winfo_rootx(),
                    window.search.winfo_rooty(),
                    window.search.winfo_width(),
                    window.search.winfo_height(),
                ),
                (
                    window.body.winfo_rootx(),
                    window.body.winfo_rooty(),
                    window.body.winfo_width(),
                    window.body.winfo_height(),
                ),
                window.footer.winfo_rooty(),
            )
        )
    for scale in (1.25, 1.5):
        ctk.set_widget_scaling(scale)
        window.geometry("980x650+0+0")
        window.update_idletasks()
        assert window.search.winfo_width() > 600
        assert window.footer.winfo_rooty() < window.winfo_rooty() + window.winfo_height()
    ctk.set_widget_scaling(1.0)
    app.set_interface_mode("advanced")
    app.update_idletasks()
    window.refresh()
    assert window.mode_label.cget("text") == "Advanced mode"
    assert controller.state.current_step_index == 3
    assert window._selected_recipe_id == "fixture-0"
    window.close()
    assert app.host_state.subscription_count("workflow-recipes") == 0
    assert controller.subscription_count() == 0
    assert not any(worker.is_alive() for worker in app._background_workers)
    app.shutdown()
    print(
        "workflow-recipes-smoke=PASS "
        f"sizes={measurements} scaling=125%,150% recipes=12 "
        "lazy=PASS singleton=PASS explicit-progression=PASS cleanup=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
