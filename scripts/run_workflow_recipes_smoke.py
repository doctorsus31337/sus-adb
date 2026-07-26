#!/usr/bin/env python3
"""Local-only GUI acceptance smoke for the Workflow Recipes center."""

from __future__ import annotations

import customtkinter as ctk

from app.core.workflow_recipes import (
    RecipeRunController,
    RecipeSpec,
    RecipeStepResult,
    RecipeStepSpec,
    StepActionClass,
)
from app.gui.main_window import SusADBWindow
from app.gui.workflow_recipes_window import WorkflowRecipesWindow


def menu_named(root, label):
    menu = root.nametowidget(root.cget("menu"))
    for index in range(menu.index("end") + 1):
        if menu.type(index) == "cascade" and menu.entrycget(index, "label") == label:
            return menu.nametowidget(menu.entrycget(index, "menu"))
    raise AssertionError(f"Missing menu: {label}")


def specifications(calls):
    values = []
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
                f"check-{index}",
                "Run a bounded local check",
                "Invoke exactly one injected callback.",
                "Prove explicit one-step execution.",
                StepActionClass.READ_ONLY,
                action_label="Run Check",
                invoke=lambda state, value=index: (
                    calls.append((value, state.selected_serial))
                    or RecipeStepResult(
                        True,
                        "Synthetic local check complete.",
                        next_guidance="Choose Continue explicitly.",
                    )
                ),
            ),
        )
        values.append(
            RecipeSpec(
                f"fixture-{index}",
                f"Fixture Recipe {index + 1}",
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
    assert app.host_state.subscription_count("workflow-recipes") == 1
    assert not app.plugin_manager._refreshed
    window.close()
    assert app.workflow_recipes_window is None
    assert app.host_state.subscription_count("workflow-recipes") == 0

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
    window.update_idletasks()
    assert len(window.library.winfo_children()) == 12
    assert not calls
    window.focus_recipe("fixture-11")
    assert "Fixture Recipe 12" == window.search.get()
    assert controller.state.recipe_id == ""
    window.search.delete(0, "end")
    window.render_library()
    window.start_recipe("fixture-0")
    assert not calls
    assert controller.state.current_step_index == 0
    window.mark_complete()
    window.continue_run()
    assert controller.state.current_step_index == 1 and not calls
    window.run_step()
    assert calls == [(0, "")]
    assert controller.state.current_step_index == 1

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
    assert controller.state.current_step_index == 1
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
