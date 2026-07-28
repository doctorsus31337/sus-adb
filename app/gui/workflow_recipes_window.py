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
    ScopedScrollableFrame,
    focused_within,
    keyboard_focus_target,
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
        self._selected_recipe_id = (
            controller.state.recipe_id if controller.active_recipe else ""
        )
        self.recipe_cards = {}
        self.footer_buttons = {}
        self.callbacks = PendingCallbackOwner(self)
        self.title(f"{METADATA.application_name} — Workflow Recipes")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 650)
        self.geometry(self._center(980, 650))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", self._escape, add="+")
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
        self.library = ScopedScrollableFrame(
            self.body,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.library.grid(row=0, column=0, sticky="nsew")
        self.library.grid_columnconfigure(0, weight=1)
        self.overview = ScopedScrollableFrame(
            self.body,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.overview.grid_columnconfigure(0, weight=1)
        self.overview_widgets = {}
        overview_fields = (
            ("title", ("Times New Roman", 24, "bold"), self.theme["gold"]),
            ("description", ("Segoe UI", 13), self.theme["text"]),
            ("metadata", ("Segoe UI", 11, "bold"), self.theme["gold"]),
            ("prerequisites", ("Segoe UI", 11), self.theme["muted"]),
            ("requirements", ("Consolas", 11), self.theme["text"]),
            ("notice", ("Segoe UI", 12, "bold"), self.theme["gold"]),
            ("outline", ("Segoe UI", 11), self.theme["text"]),
            ("active_warning", ("Segoe UI", 11, "bold"), self.theme["error"]),
        )
        for row, (name, font, color) in enumerate(overview_fields):
            label = ctk.CTkLabel(
                self.overview,
                text="",
                text_color=color,
                font=font,
                anchor="w",
                justify="left",
                wraplength=820,
            )
            label.grid(row=row, column=0, sticky="ew", padx=14, pady=6)
            self.overview_widgets[name] = label
        self.active = ScopedScrollableFrame(
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

    def _button(self, parent, text, command, column, *, row=0, primary=False):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=self.theme["red"] if primary else self.theme["panel_alt"],
            hover_color=(
                self.theme["red_hover"]
                if primary else self.theme["gold_dark"]
            ),
            text_color=self.theme["text"],
            border_width=1,
            border_color=(
                self.theme["gold"] if primary else self.theme["gold_dark"]
            ),
            width=116,
            height=34 if primary else 30,
        )
        button.grid(row=row, column=column, sticky="ew", padx=3, pady=4)
        return button

    def _build_footer(self):
        self.footer = ctk.CTkFrame(
            self,
            fg_color=self.theme["panel_alt"],
            border_width=1,
            border_color=self.theme["border"],
        )
        self.footer.grid(row=3, column=0, sticky="ew", padx=12, pady=(3, 12))
        for column in range(5):
            self.footer.grid_columnconfigure(column, weight=1)
        self.footer.grid_remove()

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
        recipe = self._recipe(recipe_id)
        self.show_library()
        if recipe is not None:
            self.search.delete(0, "end")
            self.search.insert(0, recipe.title)
            self.render_library()
            self.select_recipe(recipe_id, focus=True)
        return self.focus_window()

    def show_library(self):
        self._view = "library"
        self.overview.grid_remove()
        self.active.grid_remove()
        self.library.grid(row=0, column=0, sticky="nsew")
        self.search.configure(state="normal")
        self.refresh()
        safe_focus(self.search)
        return self

    def show_overview(self, recipe_id=None):
        selected = recipe_id or self._selected_recipe_id
        recipe = self._recipe(selected)
        if recipe is None:
            return self.show_library()
        self._selected_recipe_id = recipe.recipe_id
        self._view = "overview"
        self.library.grid_remove()
        self.active.grid_remove()
        self.overview.grid(row=0, column=0, sticky="nsew")
        self.search.configure(state="disabled")
        self.refresh()
        return self

    def show_active(self):
        if self.controller.active_recipe is None:
            return self.show_overview()
        self._view = "active"
        self.library.grid_remove()
        self.overview.grid_remove()
        self.active.grid(row=0, column=0, sticky="nsew")
        self.search.configure(state="disabled")
        self.refresh()
        return self

    def _escape(self, _event=None):
        if self._view == "active":
            recipe = self.controller.active_recipe
            self.show_overview(recipe.recipe_id if recipe else None)
        elif self._view == "overview":
            self.show_library()
        else:
            self.close()
        return "break"

    def refresh(self):
        if self._closed or not widget_exists(self):
            return
        self.mode_label.configure(text=f"{self.mode_provider().title()} mode")
        if self._view == "library":
            self.render_library()
        elif self._view == "overview":
            self.render_overview()
        else:
            self.render_active()

    def _recipe(self, recipe_id):
        return next(
            (
                recipe for recipe in self.controller.recipes
                if recipe.recipe_id == recipe_id
            ),
            None,
        )

    def _visible_recipes(self):
        query = " ".join(self.search.get().casefold().split())
        return tuple(
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

    @staticmethod
    def _named_action(verb, title, limit=48):
        label = f"{verb} {title}"
        if len(label) <= limit:
            return label
        available = max(1, limit - len(verb) - 2)
        return f"{verb} {title[:available].rstrip()}…"

    def _open_recipe_from_key(self, recipe_id):
        self.show_overview(recipe_id)
        return "break"

    def render_library(self):
        if self._closed:
            return
        focused = self.focus_get()
        focused_recipe = next(
            (
                recipe_id for recipe_id, parts in self.recipe_cards.items()
                if focused in parts.values()
            ),
            "",
        )
        for child in self.library.winfo_children():
            child.destroy()
        self.recipe_cards.clear()
        recipes = self._visible_recipes()
        visible_ids = {recipe.recipe_id for recipe in recipes}
        if self._selected_recipe_id not in visible_ids:
            self._selected_recipe_id = ""
        for row, recipe in enumerate(recipes):
            card = ctk.CTkFrame(
                self.library,
                fg_color=self.theme["panel_alt"],
                border_width=1,
                border_color=self.theme["border"],
            )
            card.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            card.grid_columnconfigure(0, weight=1)
            focus_target = keyboard_focus_target(card)
            if focus_target is not None:
                focus_target.configure(takefocus=True)
            title = ctk.CTkLabel(
                card,
                text=recipe.title,
                text_color=self.theme["gold"],
                font=("Times New Roman", 19, "bold"),
                anchor="w",
            )
            title.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            description = ctk.CTkLabel(
                card,
                text=(
                    recipe.advanced_description
                    if self.mode_provider() == "advanced"
                    else recipe.guided_description or recipe.description
                ),
                text_color=self.theme["text"],
                anchor="w",
                justify="left",
                wraplength=720,
            )
            description.grid(row=1, column=0, sticky="ew", padx=10, pady=2)
            metadata = ctk.CTkLabel(
                card,
                text=(
                    f"{recipe.category} · {recipe.estimated_complexity} · "
                    f"Prerequisites: {', '.join(recipe.prerequisites)}"
                ),
                text_color=self.theme["muted"],
                anchor="w",
                justify="left",
                wraplength=720,
            )
            metadata.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 8))
            review = ctk.CTkButton(
                card,
                text="Review",
                command=lambda value=recipe.recipe_id: self.show_overview(value),
                fg_color=self.theme["panel_alt"],
                hover_color=self.theme["gold_dark"],
                text_color=self.theme["text"],
                border_width=1,
                border_color=self.theme["gold_dark"],
                width=100,
            )
            review.grid(row=0, column=1, rowspan=3, padx=10, pady=8)
            parts = {
                "card": card,
                "focus": focus_target,
                "title": title,
                "description": description,
                "metadata": metadata,
                "review": review,
            }
            self.recipe_cards[recipe.recipe_id] = parts
            for widget in (card, title, description, metadata):
                widget.bind(
                    "<Button-1>",
                    lambda _event, value=recipe.recipe_id:
                        self.select_recipe(value),
                    add="+",
                )
                widget.bind(
                    "<Double-Button-1>",
                    lambda _event, value=recipe.recipe_id:
                        self.show_overview(value),
                    add="+",
                )
                widget.bind(
                    "<Enter>",
                    lambda _event, value=recipe.recipe_id:
                        self._paint_card(value, hovered=True),
                    add="+",
                )
                widget.bind(
                    "<Leave>",
                    lambda _event, value=recipe.recipe_id:
                        self._paint_card(value),
                    add="+",
                )
            if focus_target is not None:
                focus_target.bind(
                    "<FocusIn>",
                    lambda _event, value=recipe.recipe_id:
                        self.select_recipe(value),
                    add="+",
                )
                for sequence in ("<Return>", "<KP_Enter>"):
                    focus_target.bind(
                        sequence,
                        lambda _event, value=recipe.recipe_id:
                            self._open_recipe_from_key(value),
                        add="+",
                    )
                focus_target.bind(
                    "<space>",
                    lambda _event, value=recipe.recipe_id:
                        self.select_recipe(value),
                    add="+",
                )
                focus_target.bind(
                    "<Up>",
                    lambda _event, value=recipe.recipe_id:
                        self.move_selection(value, -1),
                    add="+",
                )
                focus_target.bind(
                    "<Down>",
                    lambda _event, value=recipe.recipe_id:
                        self.move_selection(value, 1),
                    add="+",
                )
            self._paint_card(recipe.recipe_id)
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
        active = self.controller.active_recipe
        banner = (
            f"Active recipe: {active.title} · library review does not replace it"
            if self._live_run() else
            f"{len(recipes)} recipe{'' if len(recipes) == 1 else 's'} · "
            "select a card to review it; no step runs"
        )
        self.state_label.configure(text=banner)
        self._render_footer()
        if focused_recipe in self.recipe_cards:
            safe_focus(self.recipe_cards[focused_recipe]["focus"])

    def _paint_card(self, recipe_id, *, hovered=False):
        parts = self.recipe_cards.get(recipe_id)
        if not parts or not widget_exists(parts["card"]):
            return
        selected = recipe_id == self._selected_recipe_id
        parts["card"].configure(
            fg_color=(
                self.theme["red"]
                if selected else
                self.theme["gold_dark"]
                if hovered else
                self.theme["panel_alt"]
            ),
            border_width=2 if selected else 1,
            border_color=self.theme["gold"] if selected else self.theme["border"],
        )

    def select_recipe(self, recipe_id, *, focus=False):
        if self._recipe(recipe_id) is None:
            return self
        previous = self._selected_recipe_id
        self._selected_recipe_id = recipe_id
        if previous:
            self._paint_card(previous)
        self._paint_card(recipe_id)
        if focus and recipe_id in self.recipe_cards:
            safe_focus(self.recipe_cards[recipe_id]["focus"])
        self.state_label.configure(
            text=f"Selected: {self._recipe(recipe_id).title} · Review does not start it"
        )
        return self

    def move_selection(self, recipe_id, amount):
        recipes = self._visible_recipes()
        identifiers = tuple(recipe.recipe_id for recipe in recipes)
        if recipe_id not in identifiers:
            return "break"
        index = min(max(0, identifiers.index(recipe_id) + amount), len(identifiers) - 1)
        target = identifiers[index]
        self.select_recipe(target, focus=True)
        card = self.recipe_cards[target]["card"]
        try:
            self.library._parent_canvas.yview_moveto(
                max(0, card.winfo_y() - 8)
                / max(1, self.library.winfo_reqheight())
            )
        except tk.TclError:
            pass
        return "break"

    def _projected(self):
        return RecipeProjectedState.from_host_snapshot(self.host_state.snapshot())

    def _live_run(self):
        return (
            self.controller.active_recipe is not None
            and self.controller.state.status not in {
                RecipeRunStatus.NOT_STARTED,
                RecipeRunStatus.CANCELLED,
                RecipeRunStatus.COMPLETED,
            }
        )

    def render_overview(self):
        recipe = self._recipe(self._selected_recipe_id)
        if recipe is None:
            return self.show_library()
        projected = self._projected()
        device_required = any(step.requires_device for step in recipe.steps)
        target_required = any(step.requires_target for step in recipe.steps)
        outline = "\n".join(
            f"{index}. {step.title}  [{step.classification.display_name}]"
            for index, step in enumerate(recipe.steps, 1)
        )
        self.overview_widgets["title"].configure(text=recipe.title)
        self.overview_widgets["description"].configure(
            text=(
                recipe.advanced_description
                if self.mode_provider() == "advanced"
                else recipe.guided_description or recipe.description
            )
        )
        self.overview_widgets["metadata"].configure(
            text=(
                f"Category: {recipe.category} · "
                f"Complexity: {recipe.estimated_complexity} · "
                f"Steps: {len(recipe.steps)}"
            )
        )
        self.overview_widgets["prerequisites"].configure(
            text="Prerequisites\n• " + "\n• ".join(recipe.prerequisites)
        )
        self.overview_widgets["requirements"].configure(
            text=(
                f"Known device requirement: "
                f"{projected.selected_serial or 'Selection can occur during the recipe'}"
                f"{' (required)' if device_required else ' (optional)'}\n"
                f"Known target requirement: "
                f"{projected.selected_target or 'Selection can occur during the recipe'}"
                f"{' (required)' if target_required else ' (optional)'}"
            )
        )
        self.overview_widgets["notice"].configure(
            text="Starting this recipe does not run a step."
        )
        self.overview_widgets["outline"].configure(
            text="Ordered step outline\n" + outline
        )
        active = self.controller.active_recipe
        conflict = self._live_run() and active.recipe_id != recipe.recipe_id
        same = self._live_run() and active.recipe_id == recipe.recipe_id
        self.overview_widgets["active_warning"].configure(
            text=(
                f"Active recipe: {active.title}\n\n"
                "Only one recipe can be active at a time.\n"
                f"You may review {recipe.title}, but starting it requires "
                f"completing or cancelling {active.title} first."
                if conflict else
                f"Active recipe: {active.title}\n"
                "This overview belongs to the current runtime run."
                if same else ""
            )
        )
        self.state_label.configure(text=(
            f"Active recipe: {active.title} · reviewing: {recipe.title}"
            if conflict else
            f"Reviewing {recipe.title} · no run or step has started"
        ))
        self._render_footer()

    def start_selected_recipe(self):
        recipe = self._recipe(self._selected_recipe_id)
        if recipe is None or self._live_run():
            return
        self.controller.start(recipe.recipe_id, self._projected())
        self.show_active()

    def resume_active_recipe(self):
        if self._live_run():
            self._selected_recipe_id = self.controller.active_recipe.recipe_id
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
        self.state_label.configure(text=state.message)
        self._render_footer(availability=availability)

    def _clear_footer(self):
        focused = self.focus_get()
        focused_role = next(
            (
                role for role, button in self.footer_buttons.items()
                if focused is button or focused_within(button)
            ),
            "",
        )
        for child in self.footer.winfo_children():
            child.destroy()
        self.footer_buttons.clear()
        return focused_role

    def _footer_button(
        self, role, text, command, column, *, row=0, primary=False, columnspan=1
    ):
        button = self._button(
            self.footer, text, command, column, row=row, primary=primary
        )
        if columnspan > 1:
            button.grid_configure(columnspan=columnspan)
        self.footer_buttons[role] = button
        return button

    def _render_footer(self, *, availability=None):
        focused_role = self._clear_footer()
        if self._view == "library":
            self.footer.grid_remove()
            return
        self.footer.grid()
        if self._view == "overview":
            self._footer_button(
                "back", "Back to Library", self.show_library, 0
            )
            active = self.controller.active_recipe
            if self._live_run():
                self._footer_button(
                    "primary", self._named_action("Resume", active.title),
                    self.resume_active_recipe, 1, primary=True, columnspan=3,
                )
                self._footer_button(
                    "cancel", self._named_action("Cancel", active.title, 26),
                    self.cancel_run, 1, row=1
                )
            else:
                reviewed = self._recipe(self._selected_recipe_id)
                self._footer_button(
                    "primary",
                    self._named_action("Start", reviewed.title),
                    self.start_selected_recipe,
                    1, primary=True, columnspan=3,
                )
            self._footer_button("help", "Help", self.open_help, 4)
            if active is not None and self._live_run():
                self.state_label.configure(
                    text=(
                        f"Active run preserved: {active.title}. "
                        f"Reviewing {self._recipe(self._selected_recipe_id).title}; "
                        "resume or cancel the named active recipe explicitly."
                    )
                )
        else:
            self._footer_button(
                "back", "Back to Library", self.show_library, 0
            )
            self._footer_button("help", "Help", self.open_help, 4)
            primary = self._active_primary_action(availability)
            if primary is not None:
                text, command, enabled = primary
                button = self._footer_button(
                    "primary", text, command, 1, primary=True, columnspan=3
                )
                button.configure(state="normal" if enabled else "disabled")
            state = self.controller.state
            step = self.controller.current_step
            step_status = (
                state.step_statuses[state.current_step_index]
                if step is not None else None
            )
            if step is not None and state.current_step_index > 0:
                self._footer_button(
                    "previous", "Previous Step", self.previous_step, 0, row=1
                )
            if (
                step is not None
                and step.optional
                and step_status not in {
                    RecipeStepStatus.COMPLETED,
                    RecipeStepStatus.SKIPPED,
                }
                and self._live_run()
            ):
                self._footer_button(
                    "skip", "Skip", self.skip_step, 1, row=1
                )
            if self._live_run():
                self._footer_button(
                    "cancel", "Cancel Recipe", self.cancel_run, 4, row=1
                )
        target_role = (
            focused_role
            if focused_role in self.footer_buttons
            else "primary"
            if focused_role and "primary" in self.footer_buttons
            else ""
        )
        if target_role:
            safe_focus(self.footer_buttons[target_role])

    def _active_primary_action(self, availability):
        state = self.controller.state
        step = self.controller.current_step
        if step is None:
            return None
        status = state.step_statuses[state.current_step_index]
        if state.status is RecipeRunStatus.PAUSED_STATE_CHANGED:
            return "Restart Recipe", self.restart_run, True
        if state.status in {
            RecipeRunStatus.CANCELLED,
            RecipeRunStatus.COMPLETED,
        }:
            return (
                "Review Recipe",
                lambda: self.show_overview(self.controller.state.recipe_id),
                True,
            )
        if state.status is RecipeRunStatus.RUNNING_STEP:
            return None
        if status is RecipeStepStatus.FAILED:
            return "Retry", self.retry_step, bool(availability.available)
        if status in {
            RecipeStepStatus.COMPLETED,
            RecipeStepStatus.SKIPPED,
        }:
            return "Continue", self.continue_run, True
        binding_issue = self._binding_issue(step)
        if binding_issue:
            self.state_label.configure(text=binding_issue)
            projected = self._projected()
            can_rebind = (
                (not step.requires_device or projected.device_present)
                and (not step.requires_target or projected.selected_target)
            )
            return "Restart Recipe", self.restart_run, bool(can_rebind)
        if not availability.available:
            self.state_label.configure(
                text=availability.explanation or "Current prerequisites are unavailable."
            )
            return None
        if step.invoke is not None:
            return (
                step.action_label or {
                    StepActionClass.NAVIGATION: "Open Tool",
                    StepActionClass.READ_ONLY: "Run Check",
                    StepActionClass.STATE_CHANGING: "Review Action",
                }.get(step.classification, "Run Step"),
                self.run_step,
                True,
            )
        return "Mark Complete", self.mark_complete, True

    def _binding_issue(self, step):
        state = self.controller.state
        projected = self._projected()
        if step.requires_device and (
            not state.bound_serial
            or projected.selected_serial != state.bound_serial
        ):
            return (
                "This step requires an exact bound device. "
                "Restart explicitly with the intended serial."
            )
        if step.requires_target and (
            not state.bound_target
            or projected.selected_target != state.bound_target
        ):
            return (
                "This step requires an exact bound target. "
                "Restart explicitly with the intended package."
            )
        return ""

    def restart_run(self):
        recipe = self.controller.active_recipe
        if recipe is None:
            return
        if self.confirm_callback(
            "Restart Recipe",
            (
                f"Restart {recipe.title} with the currently selected device "
                "and target? Existing runtime progress will be replaced."
            ),
        ):
            self.controller.restart_with_current_state(self._projected())
            self.show_active()

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
        try:
            self.controller.mark_complete(self._projected())
        except ValueError as exc:
            self.state_label.configure(text=str(exc))

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
