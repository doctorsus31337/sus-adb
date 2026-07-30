"""Responsive SUS Companion application shell and lazy workspace host."""

from __future__ import annotations

import threading
import sys
import time
import queue
import os
import shutil
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from app.gui.customtkinter_compat import (
    DeterministicTabview,
    install_scroll_target_guard,
    safe_focus,
)
install_scroll_target_guard(ctk.CTkScrollableFrame)

from app.core.command_runner import CommandRunner
from app.core.command_router import CommandRouter
from app.core.command_completion import (
    CommandCompletionContext,
    CommandCompletionService,
)
from app.core.contextual_assistant import ContextualAssistantService
from app.core.context_help import HelpRegistry
from app.core.device import Device
from app.core.device_manager import DeviceManager
from app.core.host_state import HostStateStore,snapshot_from_runtime
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
from app.gui.cheat_sheet_window import CheatSheetWindow
from app.gui.command_bar import CommandBar
from app.gui.console_output import ConsoleOutput
from app.gui.device_dock import DeviceDock
from app.gui.gothic_header import GothicHeader
from app.gui.menu_bar import MenuBar
from app.gui.lazy_panel_host import LazyPanelHost
from app.gui.splash_screen import SplashScreen
from app.gui.branding_images import BrandingImages
from app.gui.theme import get_theme
from app.modules.environment import EnvironmentModule
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
from app.core.interactive_sessions import InteractiveSessionManager
from app.core.guide_engine import GuideEngine,GuideState
from app.core.installed_app_discovery import ADBInstalledAppDiscovery
from app.core.learning_center import LearningCenterService,LearningProgressStore
from app.core.objection_session_recovery import ObjectionSessionRecovery
from app.core.startup_profiler import StartupProfiler
from app.core.startup_tips import load_startup_tips
from app.core.workspace_navigation import (
    PrincipalWorkspaceController,
    WorkspaceHomeState,
)
from app.gui.environment_diagnostics_window import EnvironmentDiagnosticsWindow
from app.gui.first_run_dialog import FirstRunDialog
from app.gui.crash_dialog import CrashDialog
from app.gui.addons_center import AddonsCenter
from app.gui.addon_window_host import AddonWindowHost
from app.gui.workspace_home import WorkspaceHome
from app.plugins.host_workspace import HostWorkspaceBinding


class SusADBWindow(ctk.CTk):
    BOOTSTRAP_STAGES = (
        "Tk root", "Splash", "Configuration", "Core services", "Workspace Home"
    )

    def __init__(self, *, startup_origin=None, startup_intervals=()):
        self.startup_profiler = StartupProfiler(origin=startup_origin)
        for name, started, finished in startup_intervals:
            self.startup_profiler.record_interval(name, started, finished)
        root_started = time.perf_counter()
        super().__init__()
        self.startup_profiler.record_interval("tk-root", root_started, time.perf_counter())
        self.withdraw()
        self.theme = get_theme()
        self.branding = BrandingImages()
        self.branding.apply_window_icon(self, default=True)
        tip_catalog = load_startup_tips()
        splash_started=time.perf_counter()
        with self.startup_profiler.stage("splash-construction"):
            self.splash = SplashScreen(
                self, self.theme, tip_catalog, branding=self.branding
            )
            self.splash.paint_now()
        self.startup_profiler.record_interval("first-splash-paint",splash_started,time.perf_counter(),note="Local typographic splash")
        self.splash.update_stage(2, len(self.BOOTSTRAP_STAGES), "Loading local configuration…")
        try:
            with self.startup_profiler.stage("configuration-and-logging"):
                self._initialize_configuration()
            self.splash.update_stage(3, len(self.BOOTSTRAP_STAGES), "Preparing core services…", rotate_tip=True)
            with self.startup_profiler.stage("core-services"):
                self._initialize_core_services()
            self.splash.update_stage(
                4, len(self.BOOTSTRAP_STAGES),
                "Constructing responsive Workspace Home…",
            )
            with self.startup_profiler.stage("console-shell"):
                self._initialize_shell()
            self.splash.update_stage(
                5, len(self.BOOTSTRAP_STAGES), "Workspace Home is ready."
            )
            responsive_started = time.perf_counter()
            responsive = []
            self.after_idle(lambda: responsive.append(time.perf_counter()))
            self.deiconify()
            self.update_idletasks()
            self.update()
            if responsive:
                self.startup_profiler.record_interval(
                    "first-responsive-idle", responsive_started, responsive[0],
                    note="Workspace Home shell visible",
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
        self.installed_app_discovery=ADBInstalledAppDiscovery(self.devices.adb)
        self.command_runner = CommandRunner()
        self.host_tools = HostToolResolver(self.app_config.get("executables", {}))
        self.tool_diagnostics = ToolDiagnostics(self.command_runner, resolver=self.host_tools)
        self.frida_manager = FridaManager(self.devices.adb, self.command_runner, resolver=self.host_tools)
        terminal_preference=self.app_config.get("terminal",{}).get("preference","auto")
        self.external_terminal = ExternalTerminal(configured_terminal=None if terminal_preference=="auto" else terminal_preference)
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
        self.objection_recovery = ObjectionSessionRecovery(
            self.frida_manager,
            selected_serial_provider=lambda: self.devices.selected_serial,
            adb_state_provider=lambda serial: (
                self.devices.selected.state
                if self.devices.selected and self.devices.selected.serial == serial
                else "disconnected"
            ),
        )
        self.help_registry=HelpRegistry()
        self.guide_engine=GuideEngine()
        self.script_library = ScriptLibrary(self.app_config.get("script_library_root","scripts"))
        self.frida_python = FridaPythonAdapter()
        self.script_validator = ScriptValidator()
        self.frida_runtime = FridaRuntimeManager(
            self.frida_python, self.script_library, self.script_validator,
            diagnosis_provider=self.frida_manager.diagnose,
        )
        self.command_router=CommandRouter(self.host_tools)
        self.command_completion=CommandCompletionService()
        self.interactive_sessions=InteractiveSessionManager(
            self.external_terminal,self.host_tools,
            selected_serial_provider=lambda:self.devices.selected_serial,
            adb_path_provider=lambda:self.devices.adb.adb_path,
            objection_manager=self.objection_manager,
            frida_sessions=self.frida_sessions,
            objection_recovery=self.objection_recovery,
        )
        self.contextual_assistants=ContextualAssistantService(
            self.installed_app_discovery,self.target_discovery,
            self.tool_diagnostics,self.frida_manager,
            self.interactive_sessions,self.script_library,
            selected_target_provider=lambda:self.selected_target,
        )
        self.terminal = TerminalManager(
            self.log,self.clear_console,self.host_tools,
            router=self.command_router,interactive_callback=self._interactive_command_requested,
        )
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
        self.learning_service=LearningCenterService(
            self.plugin_manager,self.plugin_registry,
            LearningProgressStore(
                self.config_manager.directory/"learning-progress.json"
            ),
        )
        self.cheat_sheet: CheatSheetWindow | None = None
        self.context_help_window=None
        self.guided_setup_window=None
        self.learning_center_window=None
        self.addons_center=None
        self.sessions_center=None
        self.command_palette=None
        self.command_palette_registry=None
        self.workflow_recipes_window=None
        self.workflow_recipe_controller=None
        self.plugin_workbench_window=None
        self.plugin_project_wizard_window=None
        self.plugin_project_wizard_controller=None
        self.about_window=None
        self._palette_shortcut_id=None
        self._palette_shortcut_previous=""
        self.addon_window_host=AddonWindowHost(
            self,self.theme,self.plugin_manager,
            self.app_config.setdefault("addon_windows",{}),
            self.refresh_devices,self.select_device,
            {
                "device-recovery":HostWorkspaceBinding(
                    self._build_device_recovery_workspace,
                    "read-selected-device",True,
                ),
                "device-rescue.panel":HostWorkspaceBinding(
                    self._build_device_recovery_workspace,
                    "read-selected-device",True,
                ),
                "readiness-advisor":HostWorkspaceBinding(
                    self._build_readiness_advisor_workspace,
                    "read-selected-device",True,
                ),
                "rootability.panel":HostWorkspaceBinding(
                    self._build_readiness_advisor_workspace,
                    "read-selected-device",True,
                ),
                "frida-assistant":HostWorkspaceBinding(
                    lambda parent:self._build_contextual_assistant(parent,"frida"),
                    "read-selected-device",
                ),
                "frida-assistant.panel":HostWorkspaceBinding(
                    lambda parent:self._build_contextual_assistant(parent,"frida"),
                    "read-selected-device",
                ),
                "objection-assistant":HostWorkspaceBinding(
                    lambda parent:self._build_contextual_assistant(parent,"objection"),
                    "read-selected-device",
                ),
                "objection-assistant.panel":HostWorkspaceBinding(
                    lambda parent:self._build_contextual_assistant(parent,"objection"),
                    "read-selected-device",
                ),
            },
            start_background=self._start_background,
            ui_dispatch=self.call_on_ui,
            navigate=self._plugin_navigation,
        )
        self.first_run_dialog = None
        self.crash_dialog = None
        self.instrumentation_panel = None
        self.script_studio_panel = None
        self._script_editor_focus = False
        self._pentest_plugin_focus = False
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
        return DeviceRecoveryPanel(
            parent,self.theme,service,ui_dispatch=self.call_on_ui,
            help_callback=self.open_context_help,
            confirm_device_change=lambda title,message:messagebox.askyesno(
                title,message,parent=parent.winfo_toplevel()
            ),
        )

    def _build_readiness_advisor_workspace(self,parent):
        from app.core.instrumentation_readiness import (
            InstrumentationReadinessService,
        )
        from app.gui.instrumentation_readiness_panel import (
            InstrumentationReadinessPanel,
        )
        service=InstrumentationReadinessService(
            self.devices.adb,self.frida_manager,
            selected_serial_provider=lambda:self.devices.selected_serial,
            session_provider=lambda:getattr(
                getattr(self,"pentest_workspace",None),"session",None
            ),
        )
        return InstrumentationReadinessPanel(
            parent,self.theme,service,
            open_apk_lab=self.open_apk_laboratory,
            help_callback=self.open_context_help,
            ui_dispatch=self.call_on_ui,
        )

    def _build_contextual_assistant(self,parent,kind):
        from app.gui.contextual_assistant_panel import ContextualAssistantPanel
        return ContextualAssistantPanel(
            parent,self.theme,self.contextual_assistants,kind,
            refresh_devices=self.refresh_devices,
            open_guided_setup=self.open_guided_setup,
            open_sessions=self.open_assistant_session,
            open_script_studio=lambda:self.navigate_workspace("Scripts"),
            open_learning=self.open_learning_center,
            open_help=self.open_context_help,
            ui_dispatch=self.call_on_ui,
        )

    def open_assistant_session(self,section):
        center=self.open_sessions_center()
        if section in center.SECTIONS:center.tabs.set(section)
        return center

    def _initialize_shell(self):

        self.title(METADATA.display_version)
        self.minsize(1100, 700)
        self.configure(fg_color=self.theme["bg"])
        self.grid_rowconfigure(2, weight=1)
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
        self.gothic_header=GothicHeader(
            self,self.theme,self.go_home,self.open_current_help,
            self.set_interface_mode,self.interface_mode,
            branding=self.branding,
        )
        self.gothic_header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(12, 6),
        )
        self.startup_profiler.record_interval("gothic-header",started,time.perf_counter())

        started=time.perf_counter()
        self.device_dock = DeviceDock(
            self,
            self.theme,
            self.refresh_devices,
            self.connect_device,
            self.select_device,
            expanded=False,
        )
        self.device_dock.grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 5)
        )
        self.device_panel = self.device_dock
        self.startup_profiler.record_interval(
            "device-dock-shell", started, time.perf_counter()
        )

        started=time.perf_counter()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 7))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.workspace = DeterministicTabview(
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
        self.workspace.grid(row=0, column=0, sticky="nsew")
        home_tab = self.workspace.add("Home")
        console_tab = self.workspace.add("Console")
        instrumentation_tab = self.workspace.add("Instrumentation")
        scripts_tab = self.workspace.add("Scripts")
        pentest_tab = self.workspace.add("Pentest")

        home_tab.configure(fg_color=self.theme["bg"])
        home_tab.grid_rowconfigure(0, weight=1)
        home_tab.grid_columnconfigure(0, weight=1)
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

        self.home_panel = WorkspaceHome(
            home_tab,
            self.theme,
            {
                "Console": lambda: self.navigate_workspace("Console"),
                "Instrumentation": lambda: self.navigate_workspace(
                    "Instrumentation"
                ),
                "Device Recovery": self.open_device_recovery,
                "Script Studio": lambda: self.navigate_workspace("Scripts"),
                "Pentest": lambda: self.navigate_workspace("Pentest"),
                "Sessions": self.open_sessions_center,
            },
            (
                ("Add-ons Center", self.open_addons_center),
                ("Learning Center", self.open_learning_center),
                ("Environment Diagnostics", self.open_environment_diagnostics),
                ("Contextual Help", self.open_current_help),
                ("Advanced Command Reference", self.open_cheat_sheet),
            ),
        )
        self.home_panel.grid(row=0, column=0, sticky="nsew")

        self.command_bar = CommandBar(
            console_tab,
            self.execute_command,
            theme=self.theme,
            completion_service=self.command_completion,
            context_provider=self._command_completion_context,
            history=self.terminal.history,
        )
        self.command_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.console = ConsoleOutput(
            console_tab,
            handoff=self.command_bar.handoff_character,
            initial_text="sus-companion > Ready.\n\n",
            fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"],
            font=self.theme["terminal_font"],
            border_width=1,
            border_color=self.theme["border"],
        )
        self.console.grid(row=1, column=0, sticky="nsew")
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

        self.workspace_controller = PrincipalWorkspaceController(
            self._show_principal_workspace,
            initial=self.app_config.get("navigation", {}).get(
                "last_principal_workspace", "Home"
            ),
        )
        self.workspace.set(self.workspace_controller.current)
        self._home_session_unsubscribe = self.interactive_sessions.subscribe(
            lambda _record: self.call_on_ui(self._refresh_home_state)
        )
        self._refresh_home_state()
        self.bind("<Alt-Home>", self._alt_home, add="+")
        self.bind("<Escape>", self._escape_shell, add="+")
        self._install_command_palette_shortcut()

        started=time.perf_counter()
        self.status_bar = StatusBar(self, self.theme)
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 12))
        self.status_bar.apply_interface_mode(self.interface_mode)
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
        return InstrumentationPanel(
            parent,self.theme,self.tool_diagnostics,self.frida_manager,
            self.objection_manager,self.target_discovery,self.frida_sessions,
            self.log,self._sync_script_target,
            interactive_sessions=self.interactive_sessions,
            installed_app_discovery=self.installed_app_discovery,
            interface_mode=self.interface_mode,
            help_callback=self.open_context_help,
            guided_setup_callback=self.open_guided_setup,
            ui_dispatch=self.call_on_ui,
        )

    def _construct_scripts(self, parent):
        from app.gui.script_studio_panel import ScriptStudioPanel
        return ScriptStudioPanel(
            parent,self.theme,self.script_library,self.frida_runtime,
            self.script_validator,self.log,
            objection_recipes=self.objection_recipes,
            show_advisories=self.app_config.get("script_studio",{}).get(
                "show_static_analysis_advisories",False
            ),
            setting_callback=self._set_script_advisories,
            launch_session_callback=self.open_script_session,
            open_folder_callback=self.open_local_directory,
            help_callback=self.open_context_help,
            editor_focus_callback=self._set_script_editor_focus,
            ui_dispatch=self.call_on_ui,
        )

    def _set_script_editor_focus(self, active):
        if getattr(self, "_shutdown_started", False):
            return
        self._script_editor_focus = bool(active)
        self._sync_script_editor_focus()

    def _set_pentest_plugin_focus(self, active):
        if getattr(self, "_shutdown_started", False):
            return
        self._pentest_plugin_focus = bool(active)
        self._sync_script_editor_focus()

    def _sync_script_editor_focus(self):
        if getattr(self, "_shutdown_started", False):
            return
        focused = (
            hasattr(self, "workspace")
            and (
                (
                    self._script_editor_focus
                    and self.workspace.get() == "Scripts"
                )
                or (
                    self._pentest_plugin_focus
                    and self.workspace.get() == "Pentest"
                )
            )
        )
        for widget in (
            getattr(self, "gothic_header", None),
            getattr(self, "device_dock", None),
            getattr(self, "status_bar", None),
        ):
            if widget is None:
                continue
            try:
                exists = bool(widget.winfo_exists())
            except tk.TclError:
                exists = False
            if not exists:
                continue
            manager = widget.winfo_manager()
            if focused and manager:
                widget.grid_remove()
            elif not focused and not manager:
                widget.grid()

    def _set_script_advisories(self, value):
        self.app_config.setdefault("script_studio",{})[
            "show_static_analysis_advisories"
        ]=bool(value)
        result=self.config_manager.save(self.app_config)
        if not result.ok:self.log(f"[CONFIG] Could not save Script Studio preference: {result.error}")

    def open_script_session(self, descriptor):
        center=self.open_sessions_center()
        center.select_script(descriptor)
        return center

    def open_local_directory(self, path):
        directory=Path(path).expanduser().resolve()
        if not directory.is_dir():
            self.log("[SCRIPT STUDIO ERROR] The containing directory is unavailable.")
            return False
        executable=(
            shutil.which("explorer.exe") or shutil.which("explorer")
            if os.name=="nt" else shutil.which("xdg-open")
        )
        if not executable:
            self.log("[SCRIPT STUDIO ERROR] No supported host folder opener was found.")
            return False
        try:
            subprocess.Popen(
                (executable,str(directory)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=os.name!="nt",
            )
        except OSError as exc:
            self.log(f"[SCRIPT STUDIO ERROR] Could not open folder: {exc}")
            return False
        return True

    def _construct_pentest(self, parent):
        from app.gui.pentest_workspace import PentestWorkspace
        return PentestWorkspace(
            parent,self.theme,"workspaces",self.frida_manager,
            self.frida_runtime,self.tool_diagnostics,self.log,
            self.navigate_workspace,adb=self.devices.adb,
            script_library=self.script_library,
            open_script_callback=self.open_generated_script,
            plugin_manager=self.plugin_manager,
            startup_profiler=self.startup_profiler,
            state_changed_callback=self._publish_host_state,
            help_callback=self.open_context_help,
            content_focus_callback=self._set_pentest_plugin_focus,
        )

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
        name = self.workspace.get()
        if name != "Console" and hasattr(self, "command_bar"):
            self.command_bar.hide_suggestions()
        if hasattr(self, "workspace_controller"):
            self.workspace_controller.adopt(name)
        self._ensure_workspace(name)
        self._sync_script_editor_focus()
        if name == "Home":
            self._refresh_home_state()
        self._focus_workspace(name)

    def _show_principal_workspace(self, name):
        if name not in self.workspace._tab_dict:
            return None
        if name != "Console" and hasattr(self, "command_bar"):
            self.command_bar.hide_suggestions()
        if self.workspace.get() != name:
            self.workspace.set(name)
        panel = self._ensure_workspace(name)
        self._sync_script_editor_focus()
        if name == "Home":
            self._refresh_home_state()
        self._focus_workspace(name)
        return panel

    def _focus_workspace(self, name):
        if name == "Home":
            self.home_panel.focus_first_card()
            return
        if name == "Console":
            safe_focus(self.command_bar.entry)
            return
        panel = self.workspace_hosts.get(name)
        safe_focus(panel.panel if panel and panel.panel is not None else panel)

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
            return self.cheat_sheet
        self.cheat_sheet = CheatSheetWindow(self, self.theme)
        return self.cheat_sheet

    def open_about(self):
        if self.about_window is not None and self.about_window.winfo_exists():
            self.about_window.deiconify()
            self.about_window.lift()
            safe_focus(self.about_window.close_button)
            return self.about_window
        from app.gui.about_window import AboutWindow
        self.about_window = AboutWindow(
            self,
            self.theme,
            self.branding,
            help_callback=lambda: self.open_context_help("learning-center"),
            on_close=lambda: setattr(self, "about_window", None),
        )
        return self.about_window

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
            self.console.append(f"{text}\n")

    def execute_command(self, command: str):
        self.terminal.execute(command)

    def _command_completion_context(self):
        """Project current immutable host state without diagnostics or discovery."""
        snapshot = self.host_state.snapshot()
        target = snapshot.selected_target
        selected_target = (
            target.identifier or target.name if target is not None else ""
        )
        return CommandCompletionContext(
            selected_serial=snapshot.selected_serial,
            selected_device_state=(
                snapshot.selected_device.state
                if snapshot.selected_device is not None else ""
            ),
            selected_target=selected_target,
            platform=os.name,
            tool_availability=tuple(
                (name, self.host_tools.cached(name))
                for name in (
                    "adb", "fastboot", "frida", "frida-ps", "frida-trace",
                    "objection",
                )
            ),
            cwd=self.terminal.cwd,
        )

    def _interactive_command_requested(self,route):
        if threading.current_thread() is not threading.main_thread():
            self.call_on_ui(self._interactive_command_requested,route);return
        self.command_bar.show_session_prompt(route,self.open_sessions_for_route)

    def open_sessions_for_route(self,route):
        center=self.open_sessions_center()
        center.open_route(route)

    def open_sessions_center(self):
        if self.sessions_center is not None and self.sessions_center.winfo_exists():
            self.sessions_center.deiconify();self.sessions_center.lift();return self.sessions_center
        from app.gui.sessions_center import SessionsCenter
        self.sessions_center=SessionsCenter(
            self,self.theme,self.interactive_sessions,self.host_state,
            target_provider=lambda:self.selected_target,
            script_library=self.script_library,
            open_script_callback=self.open_generated_script,
            help_callback=self.open_context_help,
            ui_dispatch=self.call_on_ui,
            on_close=lambda:setattr(self,"sessions_center",None),
        )
        return self.sessions_center

    def refresh_devices(self):
        if self._device_refresh_active or getattr(self,"_shutdown_started",False):return False
        self._device_refresh_active=True
        if hasattr(self, "device_dock"):
            self.device_dock.set_refreshing(True)
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
        if hasattr(self, "device_dock"):
            self.device_dock.set_refreshing(False)
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
            return False
        if (
            self.devices.selected_serial
            and serial != self.devices.selected_serial
            and not self.addon_window_host.confirm_device_change(serial)
        ):
            self._publish_host_state("device-selection-preserved")
            return False
        device = self.devices.select(serial)
        if device is None:
            self.log(f"[ADB] Device not found: {serial}")
            return False
        self._apply_device_to_workspaces(device)
        self.log(f"[ADB] Selecting {device.display_name} ({serial})...")
        BackgroundWorker(
            lambda: self.devices.adb.forward_frida_ports(serial),
            callback=lambda results: self.after(0, self._apply_connection, device, results),
        ).start()
        return True

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
        if (
            self.devices.selected_serial
            and serial != self.devices.selected_serial
            and not self.addon_window_host.confirm_device_change(serial)
        ):
            self._publish_host_state("device-selection-preserved")
            return False
        device = self.devices.select(serial)
        if device is None:
            self.log(f"[ADB] Device not found: {serial}")
            self._apply_device_to_workspaces(None)
            self._publish_host_state("device-selection-cleared")
            return False
        self._apply_device_to_workspaces(device)
        self.status_bar.set_status(
            adb="Connected" if device.connected else device.state,
            device=device.display_name,
            root="Yes" if device.root else "No",
            frida="Running" if device.frida else "Stopped",
        )
        self._publish_host_state("device-selected")
        self.log(f"[ADB] Selected {device.display_name} ({serial}).")
        return True

    def _sync_script_target(self, target):
        self.selected_target=target
        if self.script_studio_panel is not None:
            self.script_studio_panel.set_selected_target(target)
        if self.pentest_workspace is not None:
            self.pentest_workspace.set_selected_target(target)
        self._publish_host_state("target-changed")

    def _publish_host_state(self,lifecycle="ready"):
        if not hasattr(self,"host_state"):return
        target=getattr(self,"selected_target",None)
        session=getattr(getattr(self,"pentest_workspace",None),"session",None);scope=getattr(session,"scope",None)
        self.host_state.publish(snapshot_from_runtime(
            self.devices,
            selected_target=target,
            assessment_scope=scope,
            session_state=getattr(getattr(session,"state",None),"value","none"),
            interface_mode=self.interface_mode,
            lifecycle=lifecycle,
        ))
        if hasattr(self, "home_panel"):
            self._refresh_home_state()

    @property
    def interface_mode(self):
        return self.app_config.get("interface",{}).get("mode","guided")

    def set_interface_mode(self,mode):
        normalized=mode if mode in {"guided","advanced"} else "guided"
        self.app_config.setdefault("interface",{})["mode"]=normalized
        result=self.config_manager.save(self.app_config)
        if not result.ok:self.log(f"[CONFIG] Could not save interface mode: {result.error}")
        if hasattr(self,"gothic_header"):
            self.gothic_header.mode.set(normalized.title())
        if hasattr(self, "device_dock"):
            self.device_dock.apply_interface_mode(normalized)
        if hasattr(self, "status_bar"):
            self.status_bar.apply_interface_mode(normalized)
        for panel in (
            getattr(self,"instrumentation_panel",None),
            getattr(self,"script_studio_panel",None),
            getattr(self,"pentest_workspace",None),
        ):
            if panel is not None and hasattr(panel,"apply_interface_mode"):
                panel.apply_interface_mode(normalized)
        workbench=getattr(self,"plugin_workbench_window",None)
        if workbench is not None and workbench.winfo_exists():
            workbench.apply_mode()
        wizard=getattr(self,"plugin_project_wizard_window",None)
        if wizard is not None and wizard.winfo_exists():
            wizard.apply_mode()
        self._publish_host_state("interface-mode-changed")

    def _home_state(self):
        selected = self.devices.selected
        target = self.selected_target
        pentest = getattr(self, "pentest_workspace", None)
        session = getattr(pentest, "session", None)
        scope = getattr(session, "scope", None)
        scripts = getattr(self, "script_studio_panel", None)
        descriptor = getattr(scripts, "selected", None)
        active = sum(
            record.state in self.interactive_sessions.ACTIVE
            for record in self.interactive_sessions.list()
        )
        return WorkspaceHomeState(
            selected_device=selected.display_name if selected else "",
            selected_serial=selected.serial if selected else "",
            selected_target=(
                getattr(target, "identifier", None)
                or getattr(target, "name", "")
                if target else ""
            ),
            active_assessment=getattr(scope, "case_name", "") if scope else "",
            selected_script=getattr(descriptor, "name", "") if descriptor else "",
            active_sessions=active,
            interface_mode=self.interface_mode,
        )

    def _refresh_home_state(self):
        if (
            getattr(self, "_shutdown_started", False)
            or not hasattr(self, "home_panel")
        ):
            return
        self.home_panel.apply_state(self._home_state())

    def _alt_home(self, _event=None):
        self.go_home()
        return "break"

    def _escape_shell(self, _event=None):
        if hasattr(self, "device_dock") and self.device_dock.collapse():
            return "break"
        return None

    def _install_command_palette_shortcut(self):
        sequence="<Control-k>"
        self._palette_shortcut_previous=self.tk.call("bind","all",sequence)
        self._palette_shortcut_id=self.bind_all(
            sequence,self._command_palette_shortcut,add="+"
        )

    def _remove_command_palette_shortcut(self):
        if self._palette_shortcut_id is None:return
        sequence="<Control-k>"
        self.tk.call(
            "bind","all",sequence,self._palette_shortcut_previous
        )
        try:self.deletecommand(self._palette_shortcut_id)
        except tk.TclError:pass
        self._palette_shortcut_id=None

    def _command_palette_shortcut(self,event=None):
        widget=getattr(event,"widget",None)
        if event is not None and not isinstance(widget,tk.Misc):
            return None
        self.open_command_palette()
        return "break"

    def _command_palette_commands(self):
        """Project callbacks and current in-memory state into immutable commands."""
        from app.core.command_palette import PaletteCommand
        from app.plugins.addon_presenter import lifecycle_for

        mode=self.interface_mode
        snapshot=self.host_state.snapshot()
        selected_target=(
            snapshot.selected_target.identifier
            or snapshot.selected_target.name
            if snapshot.selected_target else "No target selected"
        )
        assessment=(
            snapshot.assessment_scope.case_name
            if snapshot.assessment_scope else "No active assessment"
        )
        active_sessions=sum(
            record.state in self.interactive_sessions.ACTIVE
            for record in self.interactive_sessions.list()
        )
        selected_script=getattr(
            getattr(getattr(self,"script_studio_panel",None),"selected",None),
            "name","",
        )
        technical=(
            f"Device: {snapshot.selected_serial or 'none'} · "
            f"Target: {selected_target}"
        )

        def command(
            command_id,title,description,category,aliases,callback,
            *,default_rank=100,context="",status="",hint=""
        ):
            return PaletteCommand(
                command_id,title,description,category,tuple(aliases),hint,
                True,status,command_id,"navigation",context,default_rank,
                callback,
            )

        values=[
            command(
                "workspace.home","Workspace Home",
                "Choose a principal workspace without scanning or executing.",
                "Workspaces",("home","start","workspace home"),
                lambda _query:self.navigate_workspace("Home"),default_rank=0,
                context=technical,
            ),
            command(
                "workspace.console","Console",
                "Open the local one-shot command workspace.",
                "Workspaces",("terminal","console","command line"),
                lambda _query:self.navigate_workspace("Console"),default_rank=1,
                context=technical,
            ),
            command(
                "workspace.instrumentation","Instrumentation",
                "Open target discovery and explicit observation workflows.",
                "Workspaces",("instrumentation","frida","targets"),
                lambda _query:self.navigate_workspace("Instrumentation"),
                default_rank=2,context=technical,
            ),
            command(
                "workspace.scripts","Script Studio",
                "Open the local script library and editor.",
                "Workspaces",("scripts","script studio","frida scripts"),
                lambda _query:self.navigate_workspace("Scripts"),
                default_rank=3,
                context=f"Selected script: {selected_script or 'none'}",
            ),
            command(
                "workspace.pentest","Pentest",
                "Open the authorized assessment workspace.",
                "Workspaces",("pentest","assessment","case"),
                lambda _query:self.navigate_workspace("Pentest"),
                default_rank=4,context=f"Assessment: {assessment}",
            ),
            command(
                "tool.addons","Add-ons Center",
                "Browse and manage explicit addon lifecycle steps.",
                "Tools",("addons","add-ons","plugins","plugin manager"),
                lambda _query:self.open_addons_center(),default_rank=5,
            ),
            command(
                "tool.sessions","Sessions Center",
                "Open or focus the session planner; no shell is launched.",
                "Tools",
                ("sessions","adb","adb shell","shell","objection sessions"),
                lambda _query:self.open_sessions_center(),default_rank=6,
                context=f"Active sessions: {active_sessions}",
            ),
            command(
                "tool.workflow-recipes","Workflow Recipes",
                "Open guided, operator-reviewed procedures; no step runs automatically.",
                "Tools",
                ("recipes","workflows","guided workflow","procedure","checklist"),
                lambda _query:self.open_workflow_recipes(),default_rank=7,
                context=technical,
            ),
            command(
                "tool.plugin-project-wizard","Plugin Project Wizard",
                "Create a documented, statically validated Plugin API 1.1 starter.",
                "Tools",
                (
                    "create plugin","create addon","new module","new addon",
                    "plugin wizard","addon wizard","module template",
                    "plugin scaffold","SDK project",
                ),
                lambda _query:self.open_plugin_project_wizard(),default_rank=8,
                context=technical,
            ),
            command(
                "tool.plugin-workbench","Plugin Developer Workbench",
                "Statically inspect and package a local addon without executing it.",
                "Tools",
                (
                    "plugin developer","addon developer","module checker",
                    "addon validator","inspect plugin","plugin package",
                    "package addon","plugin workbench",
                ),
                lambda _query:self.open_plugin_workbench(),default_rank=9,
            ),
            command(
                "tool.learning","Learning Center",
                "Browse local lessons, glossary entries, and bookmarks.",
                "Help",("learning","learn","tutorials"),
                lambda _query:self.open_learning_center(),default_rank=7,
            ),
            command(
                "tool.context-help","Contextual Help",
                "Search local help and glossary content.",
                "Help",
                (
                    "help","context help","glossary","adb","frida","objection",
                    *(topic.title for topic in self.help_registry.topics()),
                    *(entry.term for entry in self.help_registry.glossary()),
                ),
                lambda query:self.open_context_help_search(query),
                default_rank=8,context=f"Interface mode: {mode}",
            ),
            command(
                "tool.diagnostics","Environment Diagnostics",
                "Open local build, environment, and startup diagnostics.",
                "Tools",("diagnostics","environment","readiness"),
                lambda _query:self.open_environment_diagnostics(),
                default_rank=9,
            ),
            command(
                "tool.command-reference","Advanced Command Reference",
                "Open the read-only local command grimoire.",
                "Help",
                ("command reference","reference","grimoire","commands"),
                lambda _query:self.open_cheat_sheet(),default_rank=10,
            ),
        ]
        installed_names={
            record[2].name.casefold() for record in self.plugin_manager.records.values()
        }
        known_specs=tuple(
            card.spec for card in getattr(
                getattr(self,"addons_center",None),"cards",{}
            ).values()
            if getattr(card,"spec",None) is not None
        )
        known_names={spec.name.casefold() for spec in known_specs}
        initial_addons=(
            (
                "addon.device-rescue","Device Rescue & Recovery",
                ("rescue","recovery","broken screen","device recovery"),
            ),
            (
                "addon.frida-assistant","Frida Assistant",
                ("frida","assistant","frida help"),
            ),
            (
                "addon.objection-assistant","Objection Assistant",
                ("objection","assistant","objection help"),
            ),
        )
        for command_id,title,aliases in initial_addons:
            if title.casefold() in installed_names|known_names:continue
            values.append(command(
                command_id,title,
                "Open Add-ons Center focused on this available addon.",
                "Add-ons",aliases,
                lambda _query,value=title:self.open_addons_center(value),
                default_rank=20,
                status="Available through Add-ons Center",
            ))
        for plugin_id,record in sorted(self.plugin_manager.records.items()):
            manifest=record[2]
            panels=tuple(
                contribution for contribution
                in self.plugin_registry.by_plugin(plugin_id)
                if contribution.contribution_type=="pentest-panel"
            )
            lifecycle=lifecycle_for(
                self.plugin_manager,plugin_id,self.addon_window_host
            )
            panel=panels[0] if panels else None
            openable=panel is not None and lifecycle in {"Loaded","Window Open"}
            if openable:
                callback=(
                    lambda _query,value=panel.contribution_id:
                    self.open_addon_window(value)
                )
                description="Open or focus the existing loaded addon window."
                status=""
            else:
                callback=(
                    lambda _query,value=manifest.name:
                    self.open_addons_center(value)
                )
                description="Open Add-ons Center at this addon; no lifecycle step runs."
                status={
                    "Permissions Required":"Requires permission approval",
                    "Trust Required":"Requires package trust",
                    "Installed":"Requires Enable",
                    "Enabled":"Requires Load",
                }.get(lifecycle,f"Current state: {lifecycle}")
            presented=next(
                (spec for spec in known_specs if spec.plugin_id==plugin_id),
                None,
            )
            if presented is not None and presented.update_available:
                status=(
                    "Update review required"
                    if not presented.update_reviewed else
                    "Update ready after explicit unload"
                    if not presented.update_installable else
                    "Reviewed update ready in Add-ons Center"
                )
            values.append(command(
                f"addon.installed.{plugin_id}",manifest.name,description,
                "Add-ons",
                (
                    manifest.name,plugin_id,
                    *(component.title for component in panels),
                ),
                callback,default_rank=25,status=status,
                context=(
                    f"Package: {plugin_id} · State: {lifecycle}"
                    + (
                        f" · Contribution: {panel.contribution_id}"
                        if panel is not None else ""
                    )
                ),
            ))
        for spec in known_specs:
            if spec.plugin_id in self.plugin_manager.records:continue
            values.append(command(
                f"addon.available.{spec.plugin_id}",spec.name,
                "Open Add-ons Center focused on this available addon.",
                "Add-ons",(spec.name,spec.plugin_id),
                lambda _query,value=spec.name:self.open_addons_center(value),
                default_rank=30,status="Available · not installed",
                context=f"Package: {spec.plugin_id} · State: Available",
            ))
        for index,recipe in enumerate(self._workflow_recipe_specs()):
            values.append(command(
                f"recipe.{recipe.recipe_id}",
                f"{recipe.title} Recipe",
                recipe.description,
                "Recent",
                (*recipe.aliases,recipe.title,recipe.category,"checklist"),
                lambda _query,value=recipe.recipe_id:
                    self.open_workflow_recipes(value),
                default_rank=40+index,
                context=(
                    f"Complexity: {recipe.estimated_complexity} · "
                    "Focus only; recipe does not start automatically."
                ),
            ))
        return tuple(values)

    def _command_palette_subscriptions(self):
        def host_subscribe(refresh):
            return self.host_state.subscribe(
                "command-palette",
                lambda _snapshot:self.call_on_ui(refresh),
                replay=False,
            )
        return (
            host_subscribe,
            lambda refresh:self.plugin_manager.subscribe(
                lambda _event,_plugin:self.call_on_ui(refresh)
            ),
            lambda refresh:self.plugin_registry.subscribe(
                lambda _items:self.call_on_ui(refresh)
            ),
            lambda refresh:self.interactive_sessions.subscribe(
                lambda _record:self.call_on_ui(refresh)
            ),
        )

    def open_command_palette(self):
        if (
            self.command_palette is not None
            and self.command_palette.winfo_exists()
        ):
            return self.command_palette.focus_search()
        if self.command_palette_registry is None:
            from app.core.command_palette import CommandPaletteRegistry
            self.command_palette_registry=CommandPaletteRegistry()
        from app.gui.command_palette import CommandPaletteWindow
        self.command_palette=CommandPaletteWindow(
            self,self.theme,self.command_palette_registry,
            self._command_palette_commands,
            subscriptions=self._command_palette_subscriptions(),
            mode_provider=lambda:self.interface_mode,
            on_close=lambda:setattr(self,"command_palette",None),
        )
        return self.command_palette

    def _workflow_recipe_specs(self):
        """Return the lazy host-owned recipe catalog."""
        from app.core.workflow_recipe_catalog import (
            RecipeHostCallbacks,
            build_recipe_catalog,
        )
        return build_recipe_catalog(RecipeHostCallbacks(
            focus_device_selector=self._focus_recipe_device_selector,
            open_environment_diagnostics=self.open_environment_diagnostics,
            open_installed_applications=self._open_recipe_installed_apps,
            open_readiness_advisor=lambda:self._open_recipe_addon(
                "Instrumentation & Root Readiness Advisor",
                ("rootability.panel","readiness-advisor"),
            ),
            open_frida_assistant=lambda:self._open_recipe_addon(
                "Frida Assistant",
                ("frida-assistant.panel","frida-assistant"),
            ),
            open_frida_sessions=self._open_recipe_frida_sessions,
            open_device_recovery=lambda:self._open_recipe_addon(
                "Device Rescue & Recovery",
                ("device-rescue.panel","device-recovery"),
            ),
            open_pentest=lambda:self.navigate_workspace("Pentest"),
            open_assessment_scope=self.new_assessment_case,
            open_findings=self.open_findings,
            open_timeline=self._open_recipe_timeline,
        ))

    def _focus_recipe_device_selector(self):
        self.device_dock.expand()
        safe_focus(self.device_dock.select_button)
        return self.device_dock

    def _open_recipe_installed_apps(self):
        panel=self.navigate_workspace("Instrumentation")
        if panel is not None:
            panel.internal_workspace.set("Targets")
            panel.target_sources.set("Installed Applications")
        return panel

    def _open_recipe_addon(self,title,contribution_ids):
        contribution=next(
            (
                item for item in self.plugin_registry.list("pentest-panel")
                if item.contribution_id in set(contribution_ids)
            ),
            None,
        )
        if contribution is not None:
            return self.open_addon_window(contribution.contribution_id)
        return self.open_addons_center(title)

    def _open_recipe_frida_sessions(self):
        center=self.open_sessions_center()
        center.tabs.set("Frida REPL")
        return center

    def _open_recipe_timeline(self):
        panel=self.navigate_workspace("Pentest")
        if panel is not None:
            panel._select_section("Timeline")
        return panel

    def _workflow_recipe_controller(self):
        if self.workflow_recipe_controller is None:
            from app.core.workflow_recipes import RecipeRunController
            self.workflow_recipe_controller=RecipeRunController(
                self._workflow_recipe_specs()
            )
        return self.workflow_recipe_controller

    def open_workflow_recipes(self,recipe_id=None):
        if (
            self.workflow_recipes_window is not None
            and self.workflow_recipes_window.winfo_exists()
        ):
            if recipe_id is not None:
                return self.workflow_recipes_window.focus_recipe(recipe_id)
            return self.workflow_recipes_window.focus_window()
        from app.gui.workflow_recipes_window import WorkflowRecipesWindow
        self.workflow_recipes_window=WorkflowRecipesWindow(
            self,self.theme,self._workflow_recipe_controller(),self.host_state,
            mode_provider=lambda:self.interface_mode,
            help_callback=self.open_context_help,
            on_close=lambda:setattr(self,"workflow_recipes_window",None),
        )
        if recipe_id is not None:
            self.workflow_recipes_window.focus_recipe(recipe_id)
        return self.workflow_recipes_window

    def _plugin_workbench_installed(self):
        from app.plugins.plugin_workbench import InstalledPluginSnapshot
        self.plugin_manager.ensure_refreshed()
        return {
            plugin_id:InstalledPluginSnapshot.from_inspection(record[1])
            for plugin_id,record in self.plugin_manager.records.items()
        }

    def _plugin_workbench_official_identities(self):
        catalog = self.plugin_manager.catalog
        if catalog is None:
            return {}
        return {
            item.manifest.plugin_id: any(
                action.get("kind") == "export-template"
                for action in item.manifest.addon_ui.get("catalog_actions", ())
                if isinstance(action, dict)
            )
            for item in catalog.list(self.plugin_manager.records)
        }

    def open_plugin_workbench(self, candidate=None):
        if (
            self.plugin_workbench_window is not None
            and self.plugin_workbench_window.winfo_exists()
        ):
            window=self.plugin_workbench_window.focus_window()
            if candidate is not None:window.select_candidate(candidate)
            return window
        from app.gui.plugin_workbench_window import PluginWorkbenchWindow
        from app.plugins.plugin_workbench import PluginWorkbenchAnalyzer
        self.plugin_workbench_window=PluginWorkbenchWindow(
            self,self.theme,
            lambda cancelled:PluginWorkbenchAnalyzer(
                installed=self._plugin_workbench_installed(),
                official_identities=self._plugin_workbench_official_identities(),
                host_version=METADATA.version,cancelled=cancelled,
            ),
            start_background=self._start_background,
            install_callback=self.plugin_manager.install,
            mode_provider=lambda:self.interface_mode,
            help_callback=self.open_context_help,
            on_close=lambda:setattr(self,"plugin_workbench_window",None),
        )
        if candidate is not None:
            self.plugin_workbench_window.select_candidate(candidate)
        return self.plugin_workbench_window

    def open_plugin_project_wizard(self):
        if (
            self.plugin_project_wizard_window is not None
            and self.plugin_project_wizard_window.winfo_exists()
        ):
            return self.plugin_project_wizard_window.focus_window()
        if self.plugin_project_wizard_controller is None:
            from app.plugins.plugin_project import PluginProjectGenerator
            from app.plugins.plugin_project_wizard import (
                PluginProjectWizardController,
            )
            self.plugin_project_wizard_controller=PluginProjectWizardController(
                generator_factory=lambda:PluginProjectGenerator(
                    self._plugin_workbench_official_identities()
                )
            )
        from app.gui.plugin_project_wizard import PluginProjectWizardWindow
        self.plugin_project_wizard_window=PluginProjectWizardWindow(
            self,self.theme,self.plugin_project_wizard_controller,
            start_background=self._start_background,
            ui_dispatch=self.call_on_ui,
            mode_provider=lambda:self.interface_mode,
            workbench_callback=self.open_plugin_workbench,
            help_callback=self.open_context_help,
            on_close=lambda:setattr(
                self,"plugin_project_wizard_window",None
            ),
        )
        return self.plugin_project_wizard_window

    def current_help_topic(self):
        workspace=self.workspace.get() if hasattr(self,"workspace") else "Console"
        if workspace=="Home":return "console"
        if workspace=="Console":return "console"
        if workspace=="Instrumentation":
            panel=getattr(self,"instrumentation_panel",None)
            section=panel.internal_workspace.get() if panel else "Overview"
            return {
                "Overview":"instrumentation-overview",
                "Targets":"targets",
                "Sessions":"sessions",
            }.get(section,"instrumentation-overview")
        if workspace=="Scripts":return "script-studio"
        panel=getattr(self,"pentest_workspace",None)
        section=panel.workspace.get() if panel else "Dashboard"
        return {
            "Dashboard":"pentest-dashboard","ADB Explorer":"adb-explorer",
            "Runtime Explorer":"runtime-explorer","Network":"network",
            "Storage":"storage","APK Lab":"apk-laboratory",
            "Findings":"findings-reports","Reports":"findings-reports",
            "Plugins":"plugin-manager",
        }.get(section,"pentest-dashboard")

    def open_current_help(self):
        return self.open_context_help(self.current_help_topic())

    def open_context_help(self,topic_id="console"):
        if self.context_help_window is None or not self.context_help_window.winfo_exists():
            from app.gui.context_help_window import ContextHelpWindow
            self.context_help_window=ContextHelpWindow(
                self,self.theme,self.help_registry,
                interface_mode_provider=lambda:self.interface_mode,
                on_close=lambda:setattr(self,"context_help_window",None),
            )
        self.context_help_window.show_topic(topic_id)
        return self.context_help_window

    def open_context_help_search(self,query):
        window=self.open_context_help(self.current_help_topic())
        return window.show_search(query)

    def _guide_state(self):
        selected=self.devices.selected
        panel=getattr(self,"instrumentation_panel",None)
        diagnosis=getattr(panel,"_last_diagnosis",None)
        target=getattr(self,"selected_target",None)
        return GuideState(
            selected_serial=selected.serial if selected else "",
            adb_state=selected.state if selected else "unavailable",
            host_frida_available=bool(self.host_tools.resolve("frida")),
            frida_endpoint_reachable=bool(diagnosis and diagnosis.reachable),
            root_available=bool(selected and selected.root),
            server_available=bool(diagnosis and diagnosis.server_running),
            installed_apps_scanned=bool(
                panel and getattr(panel,"installed_scan_complete",False)
            ),
            selected_package=(
                getattr(target,"application_identifier",None) or ""
                if target else ""
            ),
            selected_target=(
                getattr(target,"identifier",None)
                or getattr(target,"name","")
                if target else ""
            ),
        )

    def open_guided_setup(self):
        if self.guided_setup_window is not None and self.guided_setup_window.winfo_exists():
            self.guided_setup_window.refresh();self.guided_setup_window.deiconify();self.guided_setup_window.lift();return self.guided_setup_window
        from app.gui.guided_setup_window import GuidedSetupWindow
        self.guided_setup_window=GuidedSetupWindow(
            self,self.theme,self.guide_engine,self._guide_state,
            open_destination=self.open_guide_destination,
            on_close=lambda:setattr(self,"guided_setup_window",None),
        )
        return self.guided_setup_window

    def open_learning_center(self,topic_id=None):
        if (
            self.learning_center_window is None
            or not self.learning_center_window.winfo_exists()
        ):
            from app.gui.learning_center_window import LearningCenterWindow
            self.learning_center_window=LearningCenterWindow(
                self,self.theme,self.learning_service,self.help_registry,
                open_addons=self.open_addons_center,
                open_help=self.open_context_help,
                interface_mode_provider=lambda:self.interface_mode,
                on_close=lambda:setattr(self,"learning_center_window",None),
            )
        if topic_id is not None:
            self.learning_center_window.show_context(topic_id)
        else:
            self.learning_center_window.deiconify()
            self.learning_center_window.lift()
        return self.learning_center_window

    def explain_current_screen(self):
        return self.open_learning_center(self.current_help_topic())

    def open_guide_destination(self,destination):
        if destination in {"console"}:return self.navigate_workspace("Console")
        if destination in {"targets","targets-installed","instrumentation-overview"}:
            panel=self.navigate_workspace("Instrumentation")
            if panel:
                panel.internal_workspace.set(
                    "Targets" if destination!="instrumentation-overview" else "Overview"
                )
                if destination=="targets-installed" and hasattr(panel,"target_sources"):
                    panel.target_sources.set("Installed Applications")
            return panel
        if destination in {"sessions-center"}:return self.open_sessions_center()
        if destination in {"script-studio"}:return self.navigate_workspace("Scripts")
        if destination in {"learning-center"} and hasattr(self,"open_learning_center"):
            return self.open_learning_center()
        if destination in {"device-rescue","readiness-advisor","webview-inspector"}:
            return self.open_addons_center()
        return self.open_context_help(destination)

    def navigate_workspace(self, name: str):
        return self.workspace_controller.navigate(name)

    def _plugin_navigation(self,spec):
        destinations={
            "workspace-home":lambda:self.navigate_workspace("Home"),
            "console":lambda:self.navigate_workspace("Console"),
            "instrumentation":lambda:self.navigate_workspace("Instrumentation"),
            "script-studio":lambda:self.navigate_workspace("Scripts"),
            "pentest":lambda:self.navigate_workspace("Pentest"),
            "addons-center":self.open_addons_center,
            "sessions-center":self.open_sessions_center,
            "workflow-recipes":self.open_workflow_recipes,
            "environment-diagnostics":self.open_environment_diagnostics,
            "contextual-help":self.open_context_help,
            "plugin-workbench":self.open_plugin_workbench,
        }
        callback=destinations.get(getattr(spec,"destination",""))
        if callback is None:return False
        callback();return True

    def go_home(self):return self.navigate_workspace("Home")

    def open_device_recovery(self):
        contribution = next(
            (
                item for item in self.plugin_registry.list("pentest-panel")
                if item.contribution_id == "device-rescue.panel"
            ),
            None,
        )
        if contribution is not None:
            return self.open_addon_window(contribution.contribution_id)
        return self.open_addons_center()

    def open_addons_center(self,focus_query=None):
        if self.addons_center is not None and self.addons_center.winfo_exists():
            self.addons_center.deiconify();self.addons_center.lift()
            if focus_query is not None:return self.addons_center.focus_addon(focus_query)
            self.addons_center.focus_force();return self.addons_center
        self.addons_center=AddonsCenter(
            self,self.theme,self.plugin_manager,self.addon_window_host,
            on_close=lambda:setattr(self,"addons_center",None),
            help_callback=self.open_context_help,
        )
        if focus_query is not None:self.addons_center.focus_addon(focus_query)
        return self.addons_center

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

    def _cancel_tk_after_callbacks(self):
        """Cancel callbacks owned by this closing Tcl interpreter."""
        try:callback_ids=tuple(self.tk.call("after","info"))
        except tk.TclError:return
        for callback_id in callback_ids:
            try:self.tk.call("after","cancel",callback_id)
            except tk.TclError:pass

    def shutdown(self):
        if getattr(self,"_shutdown_started",False):return
        shutdown_started=time.perf_counter()
        self._shutdown_started=True;life=ApplicationLifecycle(shutdown_timeout=5)
        if getattr(self,"_ui_poll_id",None):
            try:self.after_cancel(self._ui_poll_id)
            except Exception:pass
            self._ui_poll_id=None
        for host in getattr(self,"workspace_hosts",{}).values():host.shutdown()
        if getattr(self, "_home_session_unsubscribe", None):
            self._home_session_unsubscribe()
            self._home_session_unsubscribe = None
        if getattr(self,"splash",None) is not None and self.splash.winfo_exists():self.splash.close()
        if self.addons_center is not None and self.addons_center.winfo_exists():self.addons_center.close()
        if self.sessions_center is not None and self.sessions_center.winfo_exists():self.sessions_center.close()
        if self.context_help_window is not None and self.context_help_window.winfo_exists():self.context_help_window.close()
        if self.guided_setup_window is not None and self.guided_setup_window.winfo_exists():self.guided_setup_window.close()
        if self.learning_center_window is not None and self.learning_center_window.winfo_exists():self.learning_center_window.close()
        if self.command_palette is not None and self.command_palette.winfo_exists():self.command_palette.close()
        if hasattr(self, "console"):self.console.close()
        if hasattr(self, "command_bar"):self.command_bar.close()
        if self.workflow_recipes_window is not None and self.workflow_recipes_window.winfo_exists():self.workflow_recipes_window.close()
        if self.plugin_project_wizard_window is not None and self.plugin_project_wizard_window.winfo_exists():self.plugin_project_wizard_window.close()
        if self.plugin_workbench_window is not None and self.plugin_workbench_window.winfo_exists():self.plugin_workbench_window.close()
        if self.about_window is not None and self.about_window.winfo_exists():self.about_window.close()
        self._remove_command_palette_shortcut()
        for name,owner,method in (("interactive-sessions",getattr(self,"interactive_sessions",None),"shutdown"),("addon-windows",getattr(self,"addon_window_host",None),"shutdown"),("plugins",getattr(self,"plugin_manager",None),"shutdown"),("reports",getattr(getattr(self,"pentest_workspace",None),"findings_reporting",None),"cleanup"),("apk",getattr(getattr(self,"pentest_workspace",None),"apk_lab",None),"cleanup"),("storage",getattr(getattr(self,"pentest_workspace",None),"storage_workspace",None),"cleanup"),("network",getattr(getattr(self,"pentest_workspace",None),"network_workspace",None),"cleanup"),("runtime",getattr(getattr(self,"pentest_workspace",None),"runtime_explorer",None),"cleanup"),("adb-explorer",getattr(getattr(self,"pentest_workspace",None),"adb_explorer",None),"cleanup")):
            if owner is not None and hasattr(owner,method):life.add_cleanup(name,getattr(owner,method))
        life.add_cleanup("deferred-workers",self._join_background_workers)
        result=life.shutdown()
        if result.errors and hasattr(self,"logging_manager"):self.logging_manager.log("ERROR","; ".join(result.errors))
        if hasattr(self,"app_config"):
            self.app_config["window"]["geometry"]=self.geometry();self.config_manager.save(self.app_config)
        if hasattr(self,"recovery_manager"):self.recovery_manager.mark_clean_shutdown()
        self.startup_profiler.record_interval("shutdown",shutdown_started,time.perf_counter(),classification="on-demand")
        if hasattr(self,"logging_manager"):self.logging_manager.close()
        self._cancel_tk_after_callbacks()
        self.destroy()

    def copy_console_selection(self, _event=None):
        return self.console.copy_selection()

    def clear_console(self):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self.clear_console)
            return
        self.console.replace("sus-companion > Console cleared.\n\n")

    def save_console(self):
        FileManager.save_console(self.console.read())
