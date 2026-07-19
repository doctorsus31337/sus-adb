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
from app.gui.pentest_workspace import PentestWorkspace
from app.gui.menu_bar import MenuBar
from app.gui.theme import get_theme
from app.modules.environment import EnvironmentModule
from app.utils.clipboard import ClipboardManager
from app.utils.system_info import SystemInfo
from app.widgets.status_bar import StatusBar
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
from app.plugins.plugin_manager import PluginManager
from app.core.app_metadata import METADATA
from app.core.config_manager import ConfigManager
from app.core.logging_manager import LoggingManager
from app.core.recovery_manager import RecoveryManager
from app.core.crash_report import CrashReporter
from app.core.environment_diagnostics import EnvironmentDiagnostics
from app.gui.environment_diagnostics_window import EnvironmentDiagnosticsWindow
from app.gui.first_run_dialog import FirstRunDialog
from app.gui.crash_dialog import CrashDialog


class SusADBWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_manager=ConfigManager();self.config_result=self.config_manager.load();self.app_config=self.config_result.data or {};self.logging_manager=LoggingManager(self.config_manager.directory/"logs",**{"level":self.app_config.get("privacy",{}).get("log_level","INFO"),"structured":self.app_config.get("privacy",{}).get("structured_logs",True)});self.recovery_manager=RecoveryManager(self.config_manager.directory);self.previous_unclean_shutdown=self.recovery_manager.begin_startup();self.crash_reporter=CrashReporter(self.config_manager.directory/"crashes",METADATA,self.logging_manager.tail);self.diagnostics_window=None
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
        plugin_root = self.app_config.get("plugin_storage_root", "plugins")
        if not __import__("pathlib").Path(plugin_root).is_absolute():
            plugin_root = self.config_manager.directory / plugin_root
        self.plugin_store = PluginStore(plugin_root)
        self.plugin_registry = ContributionRegistry()
        self.plugin_trust = PluginTrustStore(__import__("pathlib").Path(plugin_root)/"state"/"trust.json")
        self.plugin_manager = PluginManager(
            self.plugin_store, self.plugin_trust, self.plugin_registry,
            timeline_provider=lambda: getattr(getattr(self, "pentest_workspace", None), "timeline", None),
            session_provider=lambda: getattr(getattr(self, "pentest_workspace", None), "session", None),
            device_provider=lambda: self.devices.selected,
            target_provider=lambda: getattr(getattr(self, "instrumentation_panel", None), "selected_target", None),
            evidence_provider=lambda: getattr(getattr(self, "pentest_workspace", None), "evidence", None),
            finding_provider=lambda: getattr(getattr(self, "pentest_workspace", None), "findings", None),
        )
        self.cheat_sheet: CheatSheetWindow | None = None
        self.first_run_dialog = None
        self.crash_dialog = None

        self.title(METADATA.display_version)
        self.minsize(1100, 700)
        self.configure(fg_color=self.theme["bg"])
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        MenuBar(self)
        self.create_widgets()
        self.after_idle(self.center_window)
        if self.config_result.warning and self.config_result.warning.startswith("First run"):
            self.after(50, self.open_first_run)
        if self.previous_unclean_shutdown:
            self.after(75, self.open_recovery_dialog)
        self.after(250, self.startup_check)
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        self.logging_manager.exception(f"Unhandled GUI exception: {exc_value}")
        self.crash_reporter.capture(exc_value, tuple(self.workspace._tab_dict) if hasattr(self, "workspace") else ())
        super().report_callback_exception(exc_type, exc_value, exc_traceback)

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
        pentest_tab = self.workspace.add("Pentest")

        console_tab.configure(fg_color=self.theme["bg"])
        console_tab.grid_rowconfigure(1, weight=1)
        console_tab.grid_columnconfigure(0, weight=1)
        instrumentation_tab.configure(fg_color=self.theme["bg"])
        instrumentation_tab.grid_rowconfigure(0, weight=1)
        instrumentation_tab.grid_columnconfigure(0, weight=1)
        scripts_tab.configure(fg_color=self.theme["bg"])
        scripts_tab.grid_rowconfigure(0, weight=1)
        scripts_tab.grid_columnconfigure(0, weight=1)
        pentest_tab.configure(fg_color=self.theme["bg"])
        pentest_tab.grid_rowconfigure(0, weight=1)
        pentest_tab.grid_columnconfigure(0, weight=1)

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

        self.pentest_workspace = PentestWorkspace(
            pentest_tab, self.theme, "workspaces", self.frida_manager,
            self.frida_runtime, self.tool_diagnostics, self.log, self.navigate_workspace,
            adb=self.devices.adb, script_library=self.script_library,
            open_script_callback=self.open_generated_script,
            plugin_manager=self.plugin_manager,
        )
        self.pentest_workspace.grid(row=0, column=0, sticky="nsew")

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

    def open_environment_diagnostics(self):
        if self.diagnostics_window is not None and self.diagnostics_window.winfo_exists():
            self.diagnostics_window.lift()
            return
        results = EnvironmentDiagnostics().run(self.config_manager.directory, self.app_config.get("workspace_root", "workspaces"))
        self.diagnostics_window = EnvironmentDiagnosticsWindow(self, self.theme, results)

    def open_first_run(self):
        if self.first_run_dialog is None or not self.first_run_dialog.winfo_exists():
            self.first_run_dialog = FirstRunDialog(self, self.theme)

    def open_recovery_dialog(self):
        if self.crash_dialog is None or not self.crash_dialog.winfo_exists():
            self.crash_dialog = CrashDialog(self, self.theme, "A previous unclean shutdown was detected. Your local cases and evidence were preserved.")

    def log(self, text: str):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self.log, text)
            return
        self.logging_manager.log("INFO",text);self.console.insert("end", f"{text}\n")
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
            self.pentest_workspace.set_selected_device(None)
            self.status_bar.set_status(adb="No Devices", device="None", root="Unknown", frida="Unknown")
            self.log("[ADB] No devices detected.")
            return

        selected = self.devices.selected or devices[0]
        self.device_panel.selected_serial = selected.serial
        self.instrumentation_panel.set_selected_device(selected)
        self.script_studio_panel.set_selected_device(selected)
        self.pentest_workspace.set_selected_device(selected)
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
        self.pentest_workspace.set_selected_device(device)
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
            self.pentest_workspace.set_selected_device(None)
            return
        self.instrumentation_panel.set_selected_device(device)
        self.script_studio_panel.set_selected_device(device)
        self.pentest_workspace.set_selected_device(device)
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
        if hasattr(self, "pentest_workspace"):
            self.pentest_workspace.set_selected_target(target)

    def navigate_workspace(self, name: str):
        if name in self.workspace._tab_dict:
            self.workspace.set(name)

    def enter_pentest_workspace(self):
        self.navigate_workspace("Pentest")

    def open_adb_explorer(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_adb_explorer()

    def open_runtime_explorer(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_runtime_explorer()

    def open_network_workspace(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_network()

    def open_storage_explorer(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_storage()

    def open_apk_laboratory(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_apk_lab()

    def open_findings(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_findings()

    def open_report_builder(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_report_builder()

    def open_plugin_manager(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_plugins()

    def open_generated_script(self, descriptor):
        self.navigate_workspace("Scripts")
        self.script_studio_panel.refresh_library()
        selected = next((item for item in self.script_studio_panel.descriptors if item.script_id == descriptor.script_id), descriptor)
        self.script_studio_panel.select_descriptor(selected)

    def new_assessment_case(self):
        self.enter_pentest_workspace()
        self.pentest_workspace.open_scope_dialog()

    def shutdown(self):
        if hasattr(self,"plugin_manager"):
            self.plugin_manager.shutdown()
        if hasattr(self,"pentest_workspace") and hasattr(self.pentest_workspace,"findings_reporting"):
            self.pentest_workspace.findings_reporting.cleanup()
        if hasattr(self,"pentest_workspace") and hasattr(self.pentest_workspace,"apk_lab"):
            self.pentest_workspace.apk_lab.cleanup()
        if hasattr(self,"pentest_workspace") and hasattr(self.pentest_workspace,"storage_workspace"):
            self.pentest_workspace.storage_workspace.cleanup()
        if hasattr(self,"pentest_workspace") and hasattr(self.pentest_workspace,"network_workspace"):
            self.pentest_workspace.network_workspace.cleanup()
        if hasattr(self,"pentest_workspace") and hasattr(self.pentest_workspace,"runtime_explorer"):
            self.pentest_workspace.runtime_explorer.cleanup()
        if hasattr(self,"pentest_workspace") and hasattr(self.pentest_workspace,"adb_explorer"):
            self.pentest_workspace.adb_explorer.cleanup()
        if hasattr(self,"config_manager"):self.app_config["window"]["geometry"]=self.geometry();self.config_manager.save(self.app_config)
        if hasattr(self,"recovery_manager"):self.recovery_manager.mark_clean_shutdown()
        if hasattr(self,"logging_manager"):self.logging_manager.close()
        self.destroy()

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
