"""Non-modal deterministic instrumentation guide; it performs no device action."""

from __future__ import annotations

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.core.guide_engine import GuideGoal
from app.gui.customtkinter_compat import ScopedScrollableFrame
from app.gui.read_only_text import ReadOnlyTextView


class GuidedSetupWindow(ctk.CTkToplevel):
    STEPS = (
        "Select Device",
        "Check ADB",
        "Scan Device Capabilities",
        "Check Host Frida",
        "Determine Available Routes",
        "Scan Installed Apps",
        "Select App",
        "Choose Observation Method",
        "Review Plan",
        "Open Confirmed Workflow",
    )
    STEP_GUIDANCE = (
        "Choose the authorized Android device in the device dock. Confirm its serial; this guide never substitutes another device.",
        "Confirm the selected serial is online and authorized. Resolve an offline or unauthorized ADB state before continuing.",
        "Run device readiness diagnostics to identify architecture, existing root, a running Frida Server, Gadget, emulator, or debuggable-app routes.",
        "Run Host diagnostics and require the Frida and frida-ps executables to complete their bounded version checks successfully.",
        "Use the diagnosed evidence to choose one available route. ADB-only scanning needs no Frida route; runtime observation does.",
        "Open Targets → Installed Applications and select Scan Installed Apps. The ADB result renders progressively; filters remain available while rows appear.",
        "Select the exact package or running process. Frida selectors differ: -p attaches a numeric PID, -N attaches an application by identifier, -F attaches the frontmost application, and -f spawns the named program/package.",
        "Choose attach for an already-running target or spawn to observe startup. For frida-trace, -i includes native functions matching a glob and -j includes Java methods matching a Java-method pattern.",
        "Review the route, blockers, warnings, selected serial, target, and every proposed destination below. Nothing executes from this review.",
        "Open only the reviewed destination, verify its command preview, and explicitly confirm any launch, attach, spawn, trace, or script load there.",
    )

    def __init__(
        self,
        parent,
        theme,
        engine,
        state_provider,
        *,
        open_destination=None,
        on_close=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.engine = engine
        self.state_provider = state_provider
        self.open_destination = open_destination
        self.on_close = on_close
        self.step = 0
        self.plan = None
        self.state = None
        self.title(f"{METADATA.application_name} — Guided Instrumentation Setup")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 650)
        self.geometry(self._center(980, 650))
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.refresh()

    def _center(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = min(width, screen_width), min(height, screen_height)
        return (
            f"{width}x{height}+{max(0, (screen_width-width)//2)}"
            f"+{max(0, (screen_height-height)//2)}"
        )

    def _build(self):
        ctk.CTkLabel(
            self,
            text="GUIDED INSTRUMENTATION SETUP",
            font=("Times New Roman", 24, "bold"),
            text_color=self.theme["gold"],
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(14, 5))
        goal_bar = ctk.CTkFrame(self, fg_color=self.theme["panel_alt"])
        goal_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=5)
        goal_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            goal_bar, text="What are you trying to do?",
            text_color=self.theme["gold"],
        ).grid(row=0, column=0, padx=8, pady=8)
        self.goal = ctk.CTkComboBox(
            goal_bar,
            values=[item.value for item in GuideGoal],
            state="readonly",
            command=lambda _value: self.refresh(),
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            button_color=self.theme["red"],
            button_hover_color=self.theme["red_hover"],
            dropdown_fg_color=self.theme["panel_alt"],
            dropdown_hover_color=self.theme["red"],
            text_color=self.theme["text"],
            dropdown_text_color=self.theme["text"],
        )
        self.goal.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        self.goal.set(GuideGoal.SEE_INSTALLED_APPS.value)
        self.steps = ScopedScrollableFrame(
            self,
            width=270,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
        )
        self.steps.grid(row=2, column=0, sticky="ns", padx=(14, 5), pady=5)
        self.steps.grid_columnconfigure(0, weight=1)
        self.step_buttons = []
        for index, name in enumerate(self.STEPS):
            button = ctk.CTkButton(
                self.steps,
                text=f"{index + 1}. {name}",
                command=lambda value=index: self.set_step(value),
                anchor="w",
                fg_color=self.theme["panel_alt"],
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"],
                border_width=1,
                border_color=self.theme["border"],
            )
            button.grid(row=index, column=0, sticky="ew", padx=4, pady=3)
            self.step_buttons.append(button)
        body = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["border"],
        )
        body.grid(row=2, column=1, sticky="nsew", padx=(5, 14), pady=5)
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(
            body, text="", text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w",
        )
        self.heading.grid(row=0, column=0, sticky="ew", padx=10, pady=(9, 4))
        self.details = ReadOnlyTextView(
            body,
            fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"],
            border_width=1,
            border_color=self.theme["border"],
            wrap="word",
        )
        self.details.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=7, pady=7)
        for column in range(4):
            actions.grid_columnconfigure(column, weight=1)
        self._button(actions, "Back", self.back, 0)
        self._button(actions, "Refresh State", self.refresh, 1)
        self._button(actions, "Next", self.next, 2)
        self.open_button = self._button(
            actions, "Open Reviewed Workflow", self.open_reviewed, 3
        )

    def _button(self, parent, text, command, column):
        button = ctk.CTkButton(
            parent, text=text, command=command,
            fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
            border_width=1,
            border_color=self.theme["gold_dark"],
        )
        button.grid(row=0, column=column, sticky="ew", padx=3)
        return button

    @staticmethod
    def _set_text(widget, text):
        widget.replace(text)

    def refresh(self):
        self.state = self.state_provider()
        self.plan = self.engine.plan(self.goal.get(), self.state)
        self.render()

    @classmethod
    def step_body(cls, step: int, plan, state) -> str:
        lines = [cls.STEP_GUIDANCE[step]]
        if step == 0:
            lines.extend(("", f"Current serial: {state.selected_serial or 'None selected'}"))
        elif step == 1:
            lines.extend(("", f"Current ADB state: {state.adb_state}"))
        elif step == 3:
            lines.extend(("", f"Host Frida ready: {'Yes' if state.host_frida_available else 'No'}"))
        elif step == 4:
            lines.extend(("", f"Available route: {plan.route.value}"))
        elif step == 5:
            lines.extend(("", f"Installed-app scan complete: {'Yes' if state.installed_apps_scanned else 'No'}"))
        elif step == 6:
            selected = state.selected_package or state.selected_target or "None selected"
            lines.extend(("", f"Current target: {selected}"))
        elif step == 8:
            if plan.blockers:
                lines.extend(("", "Blockers:", *(f"• {item}" for item in plan.blockers)))
            if plan.warnings:
                lines.extend(("", "Warnings:", *(f"• {item}" for item in plan.warnings)))
            lines.extend(("", "Verified next actions:"))
            lines.extend(
                f"{index}. {action.label}\n   {action.explanation}\n   Destination: {action.destination}"
                for index, action in enumerate(plan.actions, 1)
            )
        elif step == 9:
            destination = plan.actions[-1].destination if plan.actions else "No destination is available until blockers are resolved."
            lines.extend(("", f"Reviewed destination: {destination}"))
        lines.extend(("", "Safety boundary: this guide performs no device or instrumentation action."))
        return "\n".join(lines)

    def render(self):
        for index, button in enumerate(self.step_buttons):
            button.configure(
                fg_color=(
                    self.theme["red"]
                    if index == self.step else self.theme["panel_alt"]
                ),
                border_color=(
                    self.theme["gold"]
                    if index == self.step else self.theme["border"]
                ),
            )
        step_name = self.STEPS[self.step]
        self.heading.configure(text=f"Step {self.step + 1}: {step_name}")
        plan = self.plan
        self._set_text(self.details, self.step_body(self.step, plan, self.state))
        self.open_button.configure(
            state=(
                "normal"
                if self.step == len(self.STEPS) - 1 and plan.actions
                else "disabled"
            )
        )

    def set_step(self, value):
        self.step = max(0, min(len(self.STEPS) - 1, int(value)))
        self.render()

    def next(self):
        self.set_step(self.step + 1)

    def back(self):
        self.set_step(self.step - 1)

    def open_reviewed(self):
        if not self.plan.actions or not self.open_destination:
            return
        self.open_destination(self.plan.actions[-1].destination)

    def close(self):
        if self.on_close:
            self.on_close()
        self.destroy()
