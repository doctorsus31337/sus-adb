"""Lazy host-owned Workflow Recipes library and active-run window."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.core.workflow_recipes import (
    RecipeProjectedState,
    RecipeRunStatus,
    RecipeStepStatus,
    StepActionClass,
)
from app.gui.customtkinter_compat import (
    PendingCallbackOwner,
    safe_focus,
    widget_exists,
)


class WorkflowRecipesWindow(ctk.CTkToplevel):
    """Two-view recipe center; all execution decisions stay operator-owned."""

    def __init__(
        self,
        parent,
        theme,
        controller,
        host_state,
        *,
        mode_provider=lambda: "guided",
        help_callback=None,
        confirm_callback=None,
        on_close=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.controller = controller
        self.host_state = host_state
        self.mode_provider = mode_provider
        self.help_callback = help_callback
        self.confirm_callback = confirm_callback or (
            lambda title, text: messagebox.askyesno(title, text, parent=self)
        )
        self.on_close = on_close
        self._closed = False
        self._view = "library"
        self._focused_recipe_id = ""
        self.callbacks = PendingCallbackOwner(self)
        self.title(f"{METADATA.application_name} — Workflow Recipes")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 650)
        self.geometry(self._center(980, 650))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close(), add="+")
        self._build_header()
        self._build_views()
        self._build_footer()
        self.host_subscription = host_state.subscribe(
            "workflow-recipes",
            lambda snapshot: self._host_changed(snapshot),
        )
        self.run_subscription = controller.subscribe(
            lambda _state: self.request_refresh()
        )
        self.refresh()

    def _center(self, width, height):
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = min(width, screen_width), min(height, screen_height)
        parent = self.master
        if widget_exists(parent):
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        else:
            x, y = (screen_width - width) // 2, (screen_height - height) // 2
        x = min(max(0, x), max(0, screen_width - width))
        y = min(max(0, y), max(0, screen_height - height))
        return f"{width}x{height}+{x}+{y}"

    def _build_header(self):
        header = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            header,
            text="⚜ WORKFLOW RECIPES",
            text_color=self.theme["gold"],
            font=("Times New Roman", 25, "bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 2))
        self.mode_label = ctk.CTkLabel(
            header, text="", text_color=self.theme["muted"], anchor="e"
        )
        self.mode_label.grid(row=0, column=1, padx=10)
        self.search = ctk.CTkEntry(
            header,
            placeholder_text="Search guided procedures and checklists…",
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
            height=36,
        )
        self.search.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(3, 9)
        )
        self.search.bind("<KeyRelease>", lambda _event: self.render_library())
        self.state_label = ctk.CTkLabel(
            self, text="", text_color=self.theme["gold"], anchor="w"
        )
        self.state_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 3))

    def _build_views(self):
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew", padx=12, pady=3)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.library = ctk.CTkScrollableFrame(
            self.body,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.library.grid(row=0, column=0, sticky="nsew")
        self.library.grid_columnconfigure(0, weight=1)
        self.active = ctk.CTkScrollableFrame(
            self.body,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.active.grid_columnconfigure(0, weight=1)
        self.active_widgets = {}
        fields = (
            ("title", ("Times New Roman", 23, "bold"), self.theme["gold"]),
            ("progress", ("Segoe UI", 12, "bold"), self.theme["gold"]),
            ("binding", ("Consolas", 11, "bold"), self.theme["text"]),
            ("step", ("Segoe UI", 17, "bold"), self.theme["text"]),
            ("classification", ("Segoe UI", 11, "bold"), self.theme["gold"]),
            ("purpose", ("Segoe UI", 12), self.theme["text"]),
            ("prerequisites", ("Segoe UI", 11), self.theme["muted"]),
            ("preview", ("Consolas", 11), self.theme["terminal_text"]),
            ("result", ("Segoe UI", 11), self.theme["text"]),
            ("history", ("Segoe UI", 11), self.theme["muted"]),
            ("next", ("Segoe UI", 11), self.theme["gold"]),
        )
        for row, (name, font, color) in enumerate(fields):
            label = ctk.CTkLabel(
                self.active,
                text="",
                text_color=color,
                font=font,
                anchor="w",
                justify="left",
                wraplength=820,
            )
            label.grid(row=row, column=0, sticky="ew", padx=14, pady=5)
            self.active_widgets[name] = label

    def _button(self, parent, text, command, column, *, secondary=False):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=(
                self.theme["panel_alt"] if secondary else self.theme["red"]
            ),
            hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
            border_width=1,
            border_color=self.theme["gold_dark"],
            width=116,
        )
        button.grid(row=0, column=column, sticky="ew", padx=3, pady=4)
        return button

    def _build_footer(self):
        self.footer = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel_alt"],
            border_width=1,
            border_color=self.theme["border"],
        )
        self.footer.grid(row=3, column=0, sticky="ew", padx=12, pady=(3, 12))
        for column in range(9):
            self.footer.grid_columnconfigure(column, weight=1)
        self.back_button = self._button(
            self.footer, "Back to Library", self.show_library, 0, secondary=True
        )
        self.previous_button = self._button(
            self.footer, "Previous Step", self.previous_step, 1, secondary=True
        )
        self.action_button = self._button(
            self.footer, "Run Check", self.run_step, 2
        )
        self.complete_button = self._button(
            self.footer, "Mark Complete", self.mark_complete, 3
        )
        self.retry_button = self._button(
            self.footer, "Retry", self.retry_step, 4
        )
        self.skip_button = self._button(
            self.footer, "Skip", self.skip_step, 5, secondary=True
        )
        self.continue_button = self._button(
            self.footer, "Continue", self.continue_run, 6
        )
        self.cancel_button = self._button(
            self.footer, "Cancel Recipe", self.cancel_run, 7, secondary=True
        )
        self.help_button = self._button(
            self.footer, "Help", self.open_help, 8, secondary=True
        )

    def _host_changed(self, snapshot):
        if self._closed:
            return
        projected = RecipeProjectedState.from_host_snapshot(snapshot)
        self.controller.update_host_state(projected)
        self.request_refresh()

    def request_refresh(self, *_args):
        if not self._closed:
            self.callbacks.schedule_idle(self.refresh)

    def focus_window(self):
        if not self._closed:
            self.deiconify()
            self.lift()
            safe_focus(self.search)
        return self

    def focus_recipe(self, recipe_id):
        recipe = next(
            (
                item for item in self.controller.recipes
                if item.recipe_id == recipe_id
            ),
            None,
        )
        self._focused_recipe_id = recipe_id if recipe else ""
        self.show_library()
        if recipe is not None:
            self.search.delete(0, "end")
            self.search.insert(0, recipe.title)
            self.render_library()
        return self.focus_window()

    def show_library(self):
        self._view = "library"
        self.active.grid_remove()
        self.library.grid(row=0, column=0, sticky="nsew")
        self.search.configure(state="normal")
        self.refresh()
        safe_focus(self.search)
        return self

    def show_active(self):
        self._view = "active"
        self.library.grid_remove()
        self.active.grid(row=0, column=0, sticky="nsew")
        self.search.configure(state="disabled")
        self.refresh()
        return self

    def refresh(self):
        if self._closed or not widget_exists(self):
            return
        self.mode_label.configure(text=f"{self.mode_provider().title()} mode")
        if self._view == "library":
            self.render_library()
        else:
            self.render_active()

    def render_library(self):
        if self._closed:
            return
        for child in self.library.winfo_children():
            child.destroy()
        query = " ".join(self.search.get().casefold().split())
        recipes = tuple(
            recipe for recipe in self.controller.recipes
            if not query or query in " ".join(
                (
                    recipe.title,
                    recipe.description,
                    recipe.category,
                    *recipe.aliases,
                    *recipe.prerequisites,
                )
            ).casefold()
        )
        for row, recipe in enumerate(recipes):
            card = ctk.CTkFrame(
                self.library,
                fg_color=(
                    self.theme["panel_alt"]
                    if recipe.recipe_id != self._focused_recipe_id
                    else self.theme["red"]
                ),
                border_width=1,
                border_color=(
                    self.theme["gold"]
                    if recipe.recipe_id == self._focused_recipe_id
                    else self.theme["border"]
                ),
            )
            card.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card,
                text=recipe.title,
                text_color=self.theme["gold"],
                font=("Times New Roman", 19, "bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                card,
                text=recipe.description,
                text_color=self.theme["text"],
                anchor="w",
                justify="left",
                wraplength=720,
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=2)
            ctk.CTkLabel(
                card,
                text=(
                    f"{recipe.category} · {recipe.estimated_complexity} · "
                    f"Prerequisites: {', '.join(recipe.prerequisites)}"
                ),
                text_color=self.theme["muted"],
                anchor="w",
                justify="left",
                wraplength=720,
            ).grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 8))
            ctk.CTkButton(
                card,
                text="Start",
                command=lambda value=recipe.recipe_id: self.start_recipe(value),
                fg_color=self.theme["red"],
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"],
                border_width=1,
                border_color=self.theme["gold_dark"],
                width=100,
            ).grid(row=0, column=1, rowspan=3, padx=10, pady=8)
        if not recipes:
            ctk.CTkLabel(
                self.library,
                text=(
                    "No matching recipes."
                    if self.controller.recipes
                    else "The guided recipe catalog is not loaded."
                ),
                text_color=self.theme["muted"],
            ).grid(row=0, column=0, padx=10, pady=30)
        self.state_label.configure(
            text=(
                f"{len(recipes)} recipe{'' if len(recipes) == 1 else 's'} · "
                "starting never runs a step"
            )
        )

    def _projected(self):
        return RecipeProjectedState.from_host_snapshot(self.host_state.snapshot())

    def start_recipe(self, recipe_id):
        self.controller.start(recipe_id, self._projected())
        self.show_active()

    def render_active(self):
        recipe = self.controller.active_recipe
        step = self.controller.current_step
        state = self.controller.state
        if recipe is None or step is None:
            self.show_library()
            return
        index = state.current_step_index
        status = state.step_statuses[index]
        result = state.step_results[index]
        advanced = self.mode_provider() == "advanced"
        projected = self._projected()
        availability = step.availability(projected)
        completed = tuple(
            f"✓ {item.title}"
            for item, item_status in zip(recipe.steps, state.step_statuses)
            if item_status is RecipeStepStatus.COMPLETED
        )
        self.active_widgets["title"].configure(text=recipe.title)
        self.active_widgets["progress"].configure(
            text=(
                f"Step {index + 1} of {len(recipe.steps)} · "
                f"Run: {state.status.value.replace('_', ' ')}"
            )
        )
        self.active_widgets["binding"].configure(
            text=(
                f"Bound device: {state.bound_serial or 'Not bound'}\n"
                f"Bound target: {state.bound_target or 'Not bound'}"
            )
        )
        self.active_widgets["step"].configure(text=step.title)
        self.active_widgets["classification"].configure(
            text=(
                f"Classification: {step.classification.display_name} · "
                f"Step state: {status.value.replace('_', ' ')}"
            )
        )
        explanation = (
            step.explanation
            if not advanced else
            f"{step.explanation}\n\nPurpose: {step.purpose}"
        )
        self.active_widgets["purpose"].configure(text=explanation)
        self.active_widgets["prerequisites"].configure(
            text=(
                "Prerequisites: "
                + ", ".join(recipe.prerequisites)
                + (
                    f"\nUnavailable: {availability.explanation}"
                    if not availability.available else ""
                )
            )
        )
        self.active_widgets["preview"].configure(
            text="Preview\n" + step.preview(projected, advanced=advanced)
        )
        self.active_widgets["result"].configure(
            text=(
                f"Result\n{result.summary}"
                + (f"\n{result.details}" if result and result.details else "")
                if result else f"Status\n{state.message}"
            )
        )
        self.active_widgets["history"].configure(
            text="Completed steps\n" + ("\n".join(completed) or "None")
        )
        self.active_widgets["next"].configure(
            text=(
                "Next guidance\n"
                + (
                    result.next_guidance
                    if result and result.next_guidance
                    else step.next_step_guidance
                    or "Complete this step, then choose Continue explicitly."
                )
            )
        )
        blocked = state.status in {
            RecipeRunStatus.PAUSED_STATE_CHANGED,
            RecipeRunStatus.CANCELLED,
            RecipeRunStatus.COMPLETED,
        }
        action_visible = step.invoke is not None
        self.action_button.configure(
            text=step.action_label or {
                StepActionClass.NAVIGATION: "Open Tool",
                StepActionClass.READ_ONLY: "Run Check",
                StepActionClass.STATE_CHANGING: "Review Action",
            }.get(step.classification, "Continue"),
            state="normal" if action_visible and availability.available and not blocked else "disabled",
        )
        self.complete_button.configure(
            state="normal" if not blocked and status is not RecipeStepStatus.COMPLETED else "disabled"
        )
        self.retry_button.configure(
            state="normal" if not blocked and status is RecipeStepStatus.FAILED else "disabled"
        )
        self.skip_button.configure(
            state="normal" if not blocked and step.optional else "disabled"
        )
        self.continue_button.configure(
            state=(
                "normal"
                if not blocked and status in {
                    RecipeStepStatus.COMPLETED,
                    RecipeStepStatus.SKIPPED,
                }
                else "disabled"
            )
        )
        self.previous_button.configure(
            state="normal" if index > 0 else "disabled"
        )
        self.cancel_button.configure(
            state=(
                "disabled"
                if state.status in {
                    RecipeRunStatus.CANCELLED,
                    RecipeRunStatus.COMPLETED,
                }
                else "normal"
            )
        )
        self.state_label.configure(text=state.message)

    def _confirmed(self, step):
        if step.classification is not StepActionClass.STATE_CHANGING:
            return True
        return bool(
            self.confirm_callback(
                f"Confirm: {step.title}",
                (
                    f"{step.preview(self._projected(), advanced=True)}\n\n"
                    "Run only this one reviewed step?"
                ),
            )
        )

    def run_step(self):
        step = self.controller.current_step
        if step is not None and self._confirmed(step):
            self.controller.run_current(
                self._projected(),
                confirmed=step.classification is StepActionClass.STATE_CHANGING,
            )

    def retry_step(self):
        step = self.controller.current_step
        if step is not None and self._confirmed(step):
            self.controller.retry_current(
                self._projected(),
                confirmed=step.classification is StepActionClass.STATE_CHANGING,
            )

    def mark_complete(self):
        self.controller.mark_complete()

    def skip_step(self):
        try:
            self.controller.skip_current()
        except ValueError as exc:
            self.state_label.configure(text=str(exc))

    def continue_run(self):
        try:
            self.controller.continue_run()
        except ValueError as exc:
            self.state_label.configure(text=str(exc))

    def previous_step(self):
        self.controller.previous_step()

    def cancel_run(self):
        if self.confirm_callback(
            "Cancel Recipe",
            "Cancel this runtime-only recipe run? No completed action is undone.",
        ):
            self.controller.cancel()

    def open_help(self):
        if self.help_callback:
            self.help_callback("workflow-recipes")

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.callbacks.cancel_all()
        if self.host_subscription:
            self.host_subscription.cancel()
            self.host_subscription = None
        if self.run_subscription:
            self.run_subscription.cancel()
            self.run_subscription = None
        safe_focus(self.master)
        if self.on_close:
            self.on_close()
        self.destroy()
