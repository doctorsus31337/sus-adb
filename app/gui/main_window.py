"""Main SUS-ADB application window."""

from __future__ import annotations

import threading

import customtkinter as ctk

from app.core.command_runner import CommandRunner
from app.core.device import Device
from app.core.device_manager import DeviceManager
from app.core.file_manager import FileManager
from app.core.external_terminal import ExternalTerminal
from app.core.frida_manager import FridaManager
from app.core.frida_session_manager import FridaSessionManager
from app.core.frida_python_adapter import FridaPythonAdapter
from app.core.frida_runtime_manager import FridaRuntimeManager
from app.core.objection_manager import ObjectionManager
from app.core.objection_recipe_manager import ObjectionRecipeManager
from app.core.terminal_manager import TerminalManager
from app.core.tool_diagnostics import ToolDiagnostics
from app.core.target_discovery import TargetDiscovery
from app.core.script_library import ScriptLibrary
from app.core.script_validator import ScriptValidator
from app.core.worker import BackgroundWorker
from app.gui.action_panel import ActionPanel
from app.gui.cheat_sheet_window import CheatSheetWindow
from app.gui.command_bar import CommandBar
from app.gui.device_panel import DevicePanel
from app.gui.gothic_header import GothicHeader
from app.gui.instrumentation_panel import InstrumentationPanel
from app.gui.script_studio_panel import ScriptStudioPanel
from app.gui.menu_bar import MenuBar
from app.gui.theme import get_theme
from app.modules.environment import EnvironmentModule
from app.utils.clipboard import ClipboardManager
from app.utils.system_info import SystemInfo
from app.widgets.status_bar import StatusBar


class SusADBWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.theme = get_theme()
        self.devices = DeviceManager()
        self.command_runner = CommandRunner()
        self.tool_diagnostics = ToolDiagnostics(self.command_runner)
        self.frida_manager = FridaManager(self.devices.adb, self.command_runner)
        self.external_terminal = ExternalTerminal()
        self.target_discovery = TargetDiscovery(self.frida_manager)
        self.frida_sessions = FridaSessionManager(self.frida_manager, self.external_terminal)
        self.objection_manager = ObjectionManager(
            self.command_runner, self.frida_manager, self.external_terminal
        )
        self.objection_recipes = ObjectionRecipeManager(
            self.objection_manager,
            lambda: self.command_runner.run(
                (self.objection_manager.objection_path or "objection", "--help"), timeout=10
            ),
        )
        self.script_library = ScriptLibrary()
        self.frida_python = FridaPythonAdapter()
        self.script_validator = ScriptValidator()
        self.frida_runtime = FridaRuntimeManager(
            self.frida_python, self.script_library, self.script_validator,
            diagnosis_provider=self.frida_manager.diagnose,
        )
        self.terminal = TerminalManager(self.log, self.clear_console)
        self.cheat_sheet: CheatSheetWindow | None = None

        self.title("SUS-ADB Companion")
        self.minsize(1100, 700)
        self.configure(fg_color=self.theme["bg"])
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        MenuBar(self)
        self.create_widgets()
        self.after_idle(self.center_window)
        self.after(250, self.startup_check)

    def create_widgets(self):
        GothicHeader(self, self.theme).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(12, 6),
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(
            body,
            width=320,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
            corner_radius=12,
        )
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))

        ctk.CTkButton(
            left,
            text="⚔ Cheat Sheet",
            command=self.open_cheat_sheet,
            fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
            font=self.theme["button_font"],
            height=44,
        ).pack(fill="x", padx=10, pady=(15, 32))

        self.device_panel = DevicePanel(
            left,
            self.theme,
            self.refresh_devices,
            self.connect_device,
            self.select_device,
        )
        self.device_panel.pack(fill="x", padx=10, pady=(0, 18))

        self.action_panel = ActionPanel(left, self.execute_command)
        self.action_panel.pack(fill="x", padx=10, pady=(0, 15))

        self.workspace = ctk.CTkTabview(
            body,
            fg_color=self.theme["panel"],
            segmented_button_fg_color=self.theme["panel_alt"],
            segmented_button_selected_color=self.theme["red"],
            segmented_button_selected_hover_color=self.theme["red_hover"],
            segmented_button_unselected_color=self.theme["panel_alt"],
            segmented_button_unselected_hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
            border_width=1,
            border_color=self.theme["border"],
        )
        self.workspace.grid(row=0, column=1, sticky="nsew")
        console_tab = self.workspace.add("Console")
        instrumentation_tab = self.workspace.add("Instrumentation")
        scripts_tab = self.workspace.add("Scripts")

        console_tab.configure(fg_color=self.theme["bg"])
        console_tab.grid_rowconfigure(1, weight=1)
        console_tab.grid_columnconfigure(0, weight=1)
        instrumentation_tab.configure(fg_color=self.theme["bg"])
        instrumentation_tab.grid_rowconfigure(0, weight=1)
        instrumentation_tab.grid_columnconfigure(0, weight=1)
        scripts_tab.configure(fg_color=self.theme["bg"])
        scripts_tab.grid_rowconfigure(0, weight=1)
        scripts_tab.grid_columnconfigure(0, weight=1)

        self.command_bar = CommandBar(console_tab, self.execute_command)
        self.command_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.console = ctk.CTkTextbox(
            console_tab,
            fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"],
            font=self.theme["terminal_font"],
            border_width=1,
            border_color=self.theme["border"],
        )
        self.console.grid(row=1, column=0, sticky="nsew")
        self.console.insert("end", "sus-adb > Ready.\n\n")
        self.console.bind("<Control-c>", self.copy_console_selection)

        self.instrumentation_panel = InstrumentationPanel(
            instrumentation_tab,
            self.theme,
            self.tool_diagnostics,
            self.frida_manager,
            self.objection_manager,
            self.target_discovery,
            self.frida_sessions,
            self.log,
            self._sync_script_target,
        )
        self.instrumentation_panel.grid(row=0, column=0, sticky="nsew")

        self.script_studio_panel = ScriptStudioPanel(
            scripts_tab, self.theme, self.script_library, self.frida_runtime,
            self.script_validator, self.log, objection_recipes=self.objection_recipes,
        )
        self.script_studio_panel.grid(row=0, column=0, sticky="nsew")

        self.status_bar = StatusBar(self, self.theme)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))

    def center_window(self):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1400, max(1100, screen_w - 80))
        height = min(860, max(700, screen_h - 120))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def startup_check(self):
        info = SystemInfo.get()
        self.log(f"[SYSTEM] {info['platform']} {info['release']} — Python {info['python']}")
        for tool, found in EnvironmentModule.check().items():
            self.log(f"[{'OK' if found else 'MISSING'}] {tool}")
        self.refresh_devices()

    def open_cheat_sheet(self):
        if self.cheat_sheet is not None and self.cheat_sheet.winfo_exists():
            self.cheat_sheet.lift()
            return
        self.cheat_sheet = CheatSheetWindow(self, self.theme)

    def log(self, text: str):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self.log, text)
            return
        self.console.insert("end", f"{text}\n")
        self.console.see("end")

    def execute_command(self, command: str):
        self.terminal.execute(command)

    def refresh_devices(self):
        self.status_bar.set_status(adb="Scanning")
        self.log("[ADB] Scanning for devices...")
        BackgroundWorker(
            lambda: self.devices.refresh(enrich=True),
            callback=lambda devices: self.after(0, self._apply_devices, devices),
        ).start()

    def _apply_devices(self, devices: list[Device]):
        self.device_panel.update_devices(devices)
        if not devices:
            self.instrumentation_panel.set_selected_device(None)
            self.script_studio_panel.set_selected_device(None)
            self.status_bar.set_status(adb="No Devices", device="None", root="Unknown", frida="Unknown")
            self.log("[ADB] No devices detected.")
            return

        selected = self.devices.selected or devices[0]
        self.device_panel.selected_serial = selected.serial
        self.instrumentation_panel.set_selected_device(selected)
        self.script_studio_panel.set_selected_device(selected)
        self.status_bar.set_status(
            adb="Connected",
            device=selected.display_name,
            root="Yes" if selected.root else "No",
            frida="Running" if selected.frida else "Stopped",
        )
        self.log(f"[ADB] Found {len(devices)} device(s). Selected: {selected.serial}")

    def connect_device(self, serial: str | None):
        if not serial:
            self.log("[ADB] Select or refresh a device first.")
            return
        device = self.devices.select(serial)
        if device is None:
            self.log(f"[ADB] Device not found: {serial}")
            return
        self.instrumentation_panel.set_selected_device(device)
        self.script_studio_panel.set_selected_device(device)
        self.log(f"[ADB] Selecting {device.display_name} ({serial})...")
        BackgroundWorker(
            lambda: self.devices.adb.forward_frida_ports(serial),
            callback=lambda results: self.after(0, self._apply_connection, device, results),
        ).start()

    def _apply_connection(self, device: Device, results):
        first, second = results
        forwarded = first.ok and second.ok
        self.status_bar.set_status(
            adb="Connected",
            device=device.display_name,
            root="Yes" if device.root else "No",
            frida="Running" if device.frida else "Stopped",
        )
        self.log(f"[ADB] Selected {device.display_name} ({device.serial}).")
        self.log("[FRIDA] Ports 27042/27043 forwarded." if forwarded else "[FRIDA] Port forwarding failed.")
        if not forwarded:
            if first.output:
                self.log(first.output)
            if second.output:
                self.log(second.output)

    def select_device(self, serial: str):
        device = self.devices.select(serial)
        if device is None:
            self.log(f"[ADB] Device not found: {serial}")
            self.instrumentation_panel.set_selected_device(None)
            self.script_studio_panel.set_selected_device(None)
            return
        self.instrumentation_panel.set_selected_device(device)
        self.script_studio_panel.set_selected_device(device)
        self.status_bar.set_status(
            adb="Connected" if device.connected else device.state,
            device=device.display_name,
            root="Yes" if device.root else "No",
            frida="Running" if device.frida else "Stopped",
        )
        self.log(f"[ADB] Selected {device.display_name} ({serial}).")

    def _sync_script_target(self, target):
        if hasattr(self, "script_studio_panel"):
            self.script_studio_panel.set_selected_target(target)

    def copy_console_selection(self, _event=None):
        return "break" if ClipboardManager.copy(self.console) else None

    def clear_console(self):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self.clear_console)
            return
        self.console.delete("1.0", "end")
        self.console.insert("end", "sus-adb > Console cleared.\n\n")

    def save_console(self):
        FileManager.save_console(self.console.get("1.0", "end"))
