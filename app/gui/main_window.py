"""Responsive SUS Companion application shell and lazy workspace host."""

from __future__ import annotations

import threading
import sys
import time
import queue
from pathlib import Path

import customtkinter as ctk
from app.gui.customtkinter_compat import install_scroll_target_guard
install_scroll_target_guard(ctk.CTkScrollableFrame)

from app.core.command_runner import CommandRunner
from app.core.device import Device
from app.core.device_manager import DeviceManager
from app.core.host_state import DeviceState,HostStateSnapshot,HostStateStore,ScopeState,TargetState
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
from app.gui.menu_bar import MenuBar
from app.gui.lazy_panel_host import LazyPanelHost
from app.gui.splash_screen import SplashScreen
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
from app.core.application_lifecycle import ApplicationLifecycle
from app.core.crash_report import CrashReporter
from app.core.environment_diagnostics import EnvironmentDiagnostics
from app.core.host_tool_resolver import HostToolResolver
from app.core.startup_profiler import StartupProfiler
from app.core.startup_tips import load_startup_tips
from app.gui.environment_diagnostics_window import EnvironmentDiagnosticsWindow
from app.gui.first_run_dialog import FirstRunDialog
from app.gui.crash_dialog import CrashDialog
from app.gui.addons_center import AddonsCenter
from app.gui.addon_window_host import AddonWindowHost


class SusADBWindow(ctk.CTk):
    BOOTSTRAP_STAGES = ("Tk root", "Splash", "Configuration", "Core services", "Console shell")

    def __init__(self, *, startup_origin=None, startup_intervals=()):
        self.startup_profiler = StartupProfiler(origin=startup_origin)
        for name, started, finished in startup_intervals:
            self.startup_profiler.record_interval(name, started, finished)
        root_started = time.perf_counter()
        super().__init__()
        self.startup_profiler.record_interval("tk-root", root_started, time.perf_counter())
        self.withdraw()
        self.theme = get_theme()
        tip_catalog = load_startup_tips()
        splash_started=time.perf_counter()
        with self.startup_profiler.stage("splash-construction"):
            self.splash = SplashScreen(self, self.theme, tip_catalog)
            self.splash.paint_now()
        self.startup_profiler.record_interval("first-splash-paint",splash_started,time.perf_counter(),note="Local typographic splash")
        self.splash.update_stage(2, len(self.BOOTSTRAP_STAGES), "Loading local configuration…")
        try:
            with self.startup_profiler.stage("configuration-and-logging"):
                self._initialize_configuration()
            self.splash.update_stage(3, len(self.BOOTSTRAP_STAGES), "Preparing core services…", rotate_tip=True)
            with self.startup_profiler.stage("core-services"):
                self._initialize_core_services()
            self.splash.update_stage(4, len(self.BOOTSTRAP_STAGES), "Constructing responsive Console shell…")
            with self.startup_profiler.stage("console-shell"):
                self._initialize_shell()
            self.splash.update_stage(5, len(self.BOOTSTRAP_STAGES), "Console Home is ready.")
            responsive_started = time.perf_counter()
            responsive = []
            self.after_idle(lambda: responsive.append(time.perf_counter()))
            self.deiconify()
            self.update_idletasks()
            self.update()
            if responsive:
                self.startup_profiler.record_interval(
                    "first-responsive-idle", responsive_started, responsive[0], note="Console shell visible"
                )
            self.splash.close()
            self.logging_manager.log("INFO", self.startup_profiler.summary())
        except Exception as exc:
            self.splash.show_failure(type(exc).__name__,self.startup_profiler.summary())
            if hasattr(self, "logging_manager"):
                self.logging_manager.exception(f"Essential bootstrap failed: {exc}")
            self.protocol("WM_DELETE_WINDOW", self.shutdown)
            return
        if self.config_result.warning and self.config_result.warning.startswith("First run"):
            self.after(50, self.open_first_run)
        if self.previous_unclean_shutdown:
            self.after(75, self.open_recovery_dialog)
        self.after_idle(lambda: self.after(25, self.startup_check))
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

    def _initialize_configuration(self):
        with self.startup_profiler.stage("configuration-load"):
            self.config_manager=ConfigManager();self.config_result=self.config_manager.load();self.app_config=self.config_result.data or {}
        with self.startup_profiler.stage("logging-initialization"):
            self.logging_manager=LoggingManager(self.config_manager.directory/"logs",**{"level":self.app_config.get("privacy",{}).get("log_level","INFO"),"structured":self.app_config.get("privacy",{}).get("structured_logs",True)})
        with self.startup_profiler.stage("recovery-initialization"):
            self.recovery_manager=RecoveryManager(self.config_manager.directory);self.previous_unclean_shutdown=self.recovery_manager.begin_startup();self.crash_reporter=CrashReporter(self.config_manager.directory/"crashes",METADATA,self.logging_manager.tail);self.diagnostics_window=None

    def _initialize_core_services(self):
        self._ui_queue = queue.Queue()
        self._ui_poll_id = None
        self._background_workers = set()
        self.host_state=HostStateStore(self.call_on_ui)
        self.devices = DeviceManager()
        self.command_runner = CommandRunner()
        self.host_tools = HostToolResolver(self.app_config.get("executables", {}))
        self.tool_diagnostics = ToolDiagnostics(self.command_runner, resolver=self.host_tools)
        self.frida_manager = FridaManager(self.devices.adb, self.command_runner, resolver=self.host_tools)
        self.external_terminal = ExternalTerminal()
        self.target_discovery = TargetDiscovery(self.frida_manager)
        self.frida_sessions = FridaSessionManager(self.frida_manager, self.external_terminal, resolver=self.host_tools)
        self.objection_manager = ObjectionManager(
            self.command_runner, self.frida_manager, self.external_terminal, resolver=self.host_tools
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
        self.terminal = TerminalManager(self.log, self.clear_console, self.host_tools)
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
            official_root=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parents[2]))/"plugins"/"official",
            auto_refresh=False,
            host_state=self.host_state,
        )
        self.cheat_sheet: CheatSheetWindow | None = None
        self.addons_center=None
        self.addon_window_host=AddonWindowHost(self,self.theme,self.plugin_manager,self.app_config.setdefault("addon_windows",{}),self.refresh_devices,self.select_device,{"device-recovery":self._build_device_recovery_workspace})
        self.first_run_dialog = None
        self.crash_dialog = None
        self.instrumentation_panel = None
        self.script_studio_panel = None
        self.pentest_workspace = None
        self.selected_target = None
        self._deferred_started = False
        self._device_refresh_active = False
        self._diagnostics_loading = False
        self._publish_host_state()

    def _build_device_recovery_workspace(self,parent):
        from app.core.device_recovery_service import ADBRecoveryBackend,DeviceRecoveryService
        from app.gui.device_recovery_panel import DeviceRecoveryPanel
        service=DeviceRecoveryService(ADBRecoveryBackend(self.devices.adb),selected_serial_provider=lambda:self.devices.selected_serial)
        return DeviceRecoveryPanel(parent,self.theme,service,ui_dispatch=self.call_on_ui)

    def _initialize_shell(self):

        self.title(METADATA.display_version)
        self.minsize(1100, 700)
        self.configure(fg_color=self.theme["bg"])
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        with self.startup_profiler.stage("menu-bar"):
            self.menu_bar=MenuBar(self)
        self.create_widgets()
        self.center_window()
        self._ui_poll_id=self.after(15,self._poll_ui_queue)

    def call_on_ui(self,callback,*args):
        if not getattr(self,"_shutdown_started",False):self._ui_queue.put((callback,args))

    def _start_background(self,target,callback):
        worker=None
        def finished(result):
            self._background_workers.discard(worker);callback(result)
        worker=BackgroundWorker(target,callback=finished);self._background_workers.add(worker);worker.start();return worker

    def _join_background_workers(self):
        for worker in tuple(self._background_workers):worker.join(1)

    def _poll_ui_queue(self):
        if getattr(self,"_shutdown_started",False):return
        while True:
            try:callback,args=self._ui_queue.get_nowait()
            except queue.Empty:break
            try:callback(*args)
            except Exception as exc:self.report_callback_exception(type(exc),exc,exc.__traceback__)
        self._ui_poll_id=self.after(15,self._poll_ui_queue)

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        self.logging_manager.exception(f"Unhandled GUI exception: {exc_value}")
        self.crash_reporter.capture(exc_value, tuple(self.workspace._tab_dict) if hasattr(self, "workspace") else ())
        super().report_callback_exception(exc_type, exc_value, exc_traceback)

    def create_widgets(self):
        started=time.perf_counter()
        self.gothic_header=GothicHeader(self, self.theme, self.go_home)
        self.gothic_header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(12, 6),
        )
        self.startup_profiler.record_interval("gothic-header",started,time.perf_counter())

        started=time.perf_counter()
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
        self.startup_profiler.record_interval("device-sidebar-shell",started,time.perf_counter())

        started=time.perf_counter()
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
            command=self._workspace_selected,
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
        self.console.insert("end", "sus-companion > Ready.\n\n")
        self.console.bind("<Control-c>", self.copy_console_selection)
        self.startup_profiler.record_interval("console-workspace",started,time.perf_counter())

        started=time.perf_counter()
        self.workspace_hosts = {
            "Instrumentation": LazyPanelHost(
                instrumentation_tab, self.theme, "Instrumentation", self._construct_instrumentation,
                self._hydrate_instrumentation,
            ),
            "Scripts": LazyPanelHost(
                scripts_tab, self.theme, "Script Studio", self._construct_scripts,
                self._hydrate_scripts,
            ),
            "Pentest": LazyPanelHost(
                pentest_tab, self.theme, "Pentest Workspace", self._construct_pentest,
                self._hydrate_pentest,
            ),
        }
        for host in self.workspace_hosts.values():
            host.grid(row=0, column=0, sticky="nsew")
        self.startup_profiler.record_interval("lazy-workspace-placeholders",started,time.perf_counter())

        started=time.perf_counter()
        self.status_bar = StatusBar(self, self.theme)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))
        self.startup_profiler.record_interval("status-bar",started,time.perf_counter())

    def center_window(self):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1400, max(1100, screen_w - 80))
        height = min(860, max(700, screen_h - 120))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _construct_instrumentation(self, parent):
        from app.gui.instrumentation_panel import InstrumentationPanel
        return InstrumentationPanel(parent,self.theme,self.tool_diagnostics,self.frida_manager,self.objection_manager,self.target_discovery,self.frida_sessions,self.log,self._sync_script_target)

    def _construct_scripts(self, parent):
        from app.gui.script_studio_panel import ScriptStudioPanel
        return ScriptStudioPanel(parent,self.theme,self.script_library,self.frida_runtime,self.script_validator,self.log,objection_recipes=self.objection_recipes)

    def _construct_pentest(self, parent):
        from app.gui.pentest_workspace import PentestWorkspace
        return PentestWorkspace(parent,self.theme,"workspaces",self.frida_manager,self.frida_runtime,self.tool_diagnostics,self.log,self.navigate_workspace,adb=self.devices.adb,script_library=self.script_library,open_script_callback=self.open_generated_script,plugin_manager=self.plugin_manager,startup_profiler=self.startup_profiler,state_changed_callback=self._publish_host_state)

    def _hydrate_instrumentation(self, panel):
        target=self.selected_target
        self.instrumentation_panel = panel
        panel.set_selected_device(self.devices.selected)
        if target is not None:
            panel.targets=(target,);panel.select_target(target)

    def _hydrate_scripts(self, panel):
        self.script_studio_panel = panel
        panel.set_selected_device(self.devices.selected)
        panel.set_selected_target(self.selected_target)

    def _hydrate_pentest(self, panel):
        self.pentest_workspace = panel
        panel.set_selected_device(self.devices.selected)
        panel.set_selected_target(self.selected_target)

    def _workspace_selected(self):
        self._ensure_workspace(self.workspace.get())

    def _ensure_workspace(self, name):
        host = self.workspace_hosts.get(name)
        if host is None or host.panel is not None:
            return host.panel if host else None
        with self.startup_profiler.stage(f"workspace:{name.casefold()}", classification="on-demand"):
            panel = host.ensure()
        if panel is None and host.error:
            self.status_bar.set_status(adb=f"{name} failed")
        return panel

    def startup_check(self):
        if self._deferred_started or getattr(self,"_shutdown_started",False):return
        self._deferred_started=True;self.status_bar.set_status(adb="Deferred checks")
        def collect():
            try:
                with self.startup_profiler.stage("environment-diagnostics",classification="deferred"):
                    return True,SystemInfo.get(),EnvironmentModule.check()
            except Exception as exc:return False,exc,{}
        self._start_background(collect,lambda result:self.call_on_ui(self._apply_startup_check,result))

    def _apply_startup_check(self,result):
        if getattr(self,"_shutdown_started",False):return
        ok,info,tools=result
        if ok:
            self.log(f"[SYSTEM] {info['platform']} {info['release']} — Python {info['python']}")
            for tool,found in tools.items():self.log(f"[{'OK' if found else 'MISSING'}] {tool}")
        else:self.log(f"[STARTUP] Deferred diagnostics failed: {type(info).__name__}")
        self.status_bar.set_status(adb="Ready");self.refresh_devices()

    def open_cheat_sheet(self):
        if self.cheat_sheet is not None and self.cheat_sheet.winfo_exists():
            self.cheat_sheet.lift()
            return
        self.cheat_sheet = CheatSheetWindow(self, self.theme)

    def open_environment_diagnostics(self):
        if self.diagnostics_window is not None and self.diagnostics_window.winfo_exists():
            self.diagnostics_window.lift()
            return
        if self._diagnostics_loading:return
        self._diagnostics_loading=True;self.status_bar.set_status(adb="Diagnostics")
        def collect():
            try:return True,EnvironmentDiagnostics(resolver=self.host_tools).run(self.config_manager.directory,self.app_config.get("workspace_root","workspaces"))
            except Exception as exc:return False,exc
        self._start_background(collect,lambda result:self.call_on_ui(self._show_environment_diagnostics,result))

    def _show_environment_diagnostics(self,result):
        self._diagnostics_loading=False
        if getattr(self,"_shutdown_started",False):return
        ok,value=result
        if not ok:self.log(f"[DIAGNOSTICS] {type(value).__name__}");self.status_bar.set_status(adb="Diagnostics failed");return
        self.diagnostics_window=EnvironmentDiagnosticsWindow(self,self.theme,value,self.startup_profiler.summary());self.status_bar.set_status(adb="Ready")

    def open_first_run(self):
        if self.first_run_dialog is None or not self.first_run_dialog.winfo_exists():
            self.first_run_dialog = FirstRunDialog(self, self.theme)

    def open_recovery_dialog(self):
        if self.crash_dialog is None or not self.crash_dialog.winfo_exists():
            self.crash_dialog = CrashDialog(self, self.theme, "A previous unclean shutdown was detected. Your local cases and evidence were preserved.")

    def log(self, text: str):
        if threading.current_thread() is not threading.main_thread():
            self.call_on_ui(self.log,text)
            return
        if hasattr(self,"logging_manager"):self.logging_manager.log("INFO",text)
        if hasattr(self,"console"):
            self.console.insert("end", f"{text}\n");self.console.see("end")

    def execute_command(self, command: str):
        self.terminal.execute(command)

    def refresh_devices(self):
        if self._device_refresh_active or getattr(self,"_shutdown_started",False):return False
        self._device_refresh_active=True
        self.status_bar.set_status(adb="Scanning")
        self._publish_host_state("device-refreshing")
        self.log("[ADB] Scanning for devices...")
        def scan():
            try:
                with self.startup_profiler.stage("device-discovery",classification="deferred"):
                    return True,self.devices.refresh(enrich=True)
            except Exception as exc:return False,exc
        self._start_background(
            scan,
            lambda result: self.call_on_ui(self._finish_device_refresh,result),
        )
        return True

    def _finish_device_refresh(self,result):
        self._device_refresh_active=False
        if getattr(self,"_shutdown_started",False):return
        ok,value=result
        if not ok:self.status_bar.set_status(adb="Scan failed");self._publish_host_state("device-refresh-failed");self.log(f"[ADB] Discovery failed: {type(value).__name__}");return
        self._apply_devices(value)

    def _apply_device_to_workspaces(self,device):
        for panel in (self.instrumentation_panel,self.script_studio_panel,self.pentest_workspace):
            if panel is not None:panel.set_selected_device(device)

    def _apply_devices(self, devices: list[Device]):
        self.device_panel.update_devices(devices)
        if not devices:
            self._apply_device_to_workspaces(None)
            self.status_bar.set_status(adb="No Devices", device="None", root="Unknown", frida="Unknown")
            self._publish_host_state("device-refresh-complete")
            self.log("[ADB] No devices detected.")
            return

        selected = self.devices.selected
        self.device_panel.selected_serial = selected.serial if selected else None
        self._apply_device_to_workspaces(selected)
        if selected:
            self.status_bar.set_status(adb="Connected" if selected.connected else selected.state,device=selected.display_name,root="Yes" if selected.root else "No",frida="Running" if selected.frida else "Stopped")
            message=f"Selected: {selected.serial}"
        else:
            self.status_bar.set_status(adb="Devices Found",device="Select Device",root="Unknown",frida="Unknown");message="Explicit selection required"
        self._publish_host_state("device-refresh-complete")
        self.log(f"[ADB] Found {len(devices)} device(s). {message}")

    def connect_device(self, serial: str | None):
        if not serial:
            self.log("[ADB] Select or refresh a device first.")
            return
        device = self.devices.select(serial)
        if device is None:
            self.log(f"[ADB] Device not found: {serial}")
            return
        self._apply_device_to_workspaces(device)
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
        self._publish_host_state("device-connected")

    def select_device(self, serial: str):
        device = self.devices.select(serial)
        if device is None:
            self.log(f"[ADB] Device not found: {serial}")
            self._apply_device_to_workspaces(None)
            self._publish_host_state("device-selection-cleared")
            return
        self._apply_device_to_workspaces(device)
        self.status_bar.set_status(
            adb="Connected" if device.connected else device.state,
            device=device.display_name,
            root="Yes" if device.root else "No",
            frida="Running" if device.frida else "Stopped",
        )
        self._publish_host_state("device-selected")
        self.log(f"[ADB] Selected {device.display_name} ({serial}).")

    def _sync_script_target(self, target):
        self.selected_target=target
        if self.script_studio_panel is not None:
            self.script_studio_panel.set_selected_target(target)
        if self.pentest_workspace is not None:
            self.pentest_workspace.set_selected_target(target)
        self._publish_host_state("target-changed")

    def _publish_host_state(self,lifecycle="ready"):
        if not hasattr(self,"host_state"):return
        devices=tuple(DeviceState(device.serial,device.model,device.manufacturer,device.state,device.display_name,bool(device.root)) for device in self.devices.all()) if hasattr(self,"devices") else ()
        selected=self.devices.selected if hasattr(self,"devices") else None
        selected_state=DeviceState(selected.serial,selected.model,selected.manufacturer,selected.state,selected.display_name,bool(selected.root)) if selected else None
        target=getattr(self,"selected_target",None)
        target_state=TargetState(getattr(target,"name",""),getattr(target,"identifier","") or "",getattr(target,"pid",None),getattr(getattr(target,"target_type",None),"value","")) if target else None
        session=getattr(getattr(self,"pentest_workspace",None),"session",None);scope=getattr(session,"scope",None)
        scope_state=ScopeState(scope.scope_id,scope.case_name,scope.authorization_confirmed,tuple(scope.allowed_actions),tuple(scope.excluded_actions)) if scope else None
        adb_state=selected.state if selected else ("available" if devices else "unavailable")
        self.host_state.publish(HostStateSnapshot(selected_state,devices,adb_state,target_state,scope_state,getattr(getattr(session,"state",None),"value","none"),self.app_config.get("interface_mode","advanced"),lifecycle))

    def navigate_workspace(self, name: str):
        if name in self.workspace._tab_dict:
            self.workspace.set(name)
            return self._ensure_workspace(name)

    def go_home(self):self.navigate_workspace("Console")

    def open_addons_center(self):
        if self.addons_center is not None and self.addons_center.winfo_exists():self.addons_center.deiconify();self.addons_center.lift();self.addons_center.focus_force();return self.addons_center
        self.addons_center=AddonsCenter(self,self.theme,self.plugin_manager,self.addon_window_host,on_close=lambda:setattr(self,"addons_center",None));return self.addons_center

    def open_addon_window(self,contribution_id):return self.addon_window_host.open(contribution_id)

    def unload_all_addons(self):
        for plugin_id,status in tuple(self.plugin_manager.loader.statuses.items()):
            if status.state.value=="active":self.plugin_manager.unload(plugin_id)

    def enter_pentest_workspace(self):
        return self.navigate_workspace("Pentest")

    def open_adb_explorer(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_adb_explorer()

    def open_runtime_explorer(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_runtime_explorer()

    def open_network_workspace(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_network()

    def open_storage_explorer(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_storage()

    def open_apk_laboratory(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_apk_lab()

    def open_findings(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_findings()

    def open_report_builder(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_report_builder()

    def open_plugin_manager(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_plugins()

    def open_plugin_contribution(self,contribution_id):
        contribution=next((c for c in self.plugin_registry.list("pentest-panel") if c.contribution_id==contribution_id),None)
        if contribution and contribution.metadata.get("ui_mode","embedded") in {"window","hybrid"}:return self.open_addon_window(contribution_id)
        self.open_plugin_manager()
        if hasattr(self.pentest_workspace,"plugin_panel"):self.pentest_workspace.plugin_panel.open_contribution(contribution_id)

    def open_generated_script(self, descriptor):
        panel=self.navigate_workspace("Scripts")
        if not panel:return
        panel.refresh_library();selected=next((item for item in panel.descriptors if item.script_id==descriptor.script_id),descriptor);panel.select_descriptor(selected)

    def new_assessment_case(self):
        panel=self.enter_pentest_workspace()
        if panel:panel.open_scope_dialog()

    def shutdown(self):
        if getattr(self,"_shutdown_started",False):return
        shutdown_started=time.perf_counter()
        self._shutdown_started=True;life=ApplicationLifecycle(shutdown_timeout=5)
        if getattr(self,"_ui_poll_id",None):
            try:self.after_cancel(self._ui_poll_id)
            except Exception:pass
            self._ui_poll_id=None
        for host in getattr(self,"workspace_hosts",{}).values():host.shutdown()
        if getattr(self,"splash",None) is not None and self.splash.winfo_exists():self.splash.close()
        if self.addons_center is not None and self.addons_center.winfo_exists():self.addons_center.close()
        for name,owner,method in (("addon-windows",getattr(self,"addon_window_host",None),"shutdown"),("plugins",getattr(self,"plugin_manager",None),"shutdown"),("reports",getattr(getattr(self,"pentest_workspace",None),"findings_reporting",None),"cleanup"),("apk",getattr(getattr(self,"pentest_workspace",None),"apk_lab",None),"cleanup"),("storage",getattr(getattr(self,"pentest_workspace",None),"storage_workspace",None),"cleanup"),("network",getattr(getattr(self,"pentest_workspace",None),"network_workspace",None),"cleanup"),("runtime",getattr(getattr(self,"pentest_workspace",None),"runtime_explorer",None),"cleanup"),("adb-explorer",getattr(getattr(self,"pentest_workspace",None),"adb_explorer",None),"cleanup")):
            if owner is not None and hasattr(owner,method):life.add_cleanup(name,getattr(owner,method))
        life.add_cleanup("deferred-workers",self._join_background_workers)
        result=life.shutdown()
        if result.errors and hasattr(self,"logging_manager"):self.logging_manager.log("ERROR","; ".join(result.errors))
        if hasattr(self,"app_config"):
            self.app_config["window"]["geometry"]=self.geometry();self.config_manager.save(self.app_config)
        if hasattr(self,"recovery_manager"):self.recovery_manager.mark_clean_shutdown()
        self.startup_profiler.record_interval("shutdown",shutdown_started,time.perf_counter(),classification="on-demand")
        if hasattr(self,"logging_manager"):self.logging_manager.close()
        self.destroy()

    def copy_console_selection(self, _event=None):
        return "break" if ClipboardManager.copy(self.console) else None

    def clear_console(self):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self.clear_console)
            return
        self.console.delete("1.0", "end")
        self.console.insert("end", "sus-companion > Console cleared.\n\n")

    def save_console(self):
        FileManager.save_console(self.console.get("1.0", "end"))
