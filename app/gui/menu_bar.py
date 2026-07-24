import tkinter as tk
from tkinter import messagebox
from app.core.app_metadata import METADATA

MENU_FONT = ("Segoe UI", 13)


class MenuBar:

    def __init__(self, window):

        self.window = window

        menu = tk.Menu(window)

        file_menu = tk.Menu(menu, tearoff=False, font=MENU_FONT)
        file_menu.add_command(label="Save Console", command=window.save_console)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=window.shutdown)
        menu.add_cascade(label="File", menu=file_menu)

        settings_menu = tk.Menu(menu, tearoff=False, font=MENU_FONT)
        settings_menu.add_command(
            label="Guided Mode",
            command=lambda: window.set_interface_mode("guided"),
        )
        settings_menu.add_command(
            label="Advanced Mode",
            command=lambda: window.set_interface_mode("advanced"),
        )
        menu.add_cascade(label="Settings", menu=settings_menu)

        tools_menu = tk.Menu(menu, tearoff=False, font=MENU_FONT)
        tools_menu.add_command(label="Refresh Devices", command=window.refresh_devices)
        tools_menu.add_command(label="Clear Console", command=window.clear_console)
        tools_menu.add_command(label="Environment Diagnostics", command=window.open_environment_diagnostics)
        tools_menu.add_command(label="Sessions Center", command=window.open_sessions_center)
        tools_menu.add_separator()
        tools_menu.add_command(label="Enter Pentest Workspace", command=window.enter_pentest_workspace)
        tools_menu.add_command(label="Open ADB Explorer", command=window.open_adb_explorer)
        tools_menu.add_command(label="Open Runtime Explorer", command=window.open_runtime_explorer)
        tools_menu.add_command(label="Open Network Workspace", command=window.open_network_workspace)
        tools_menu.add_command(label="Open Storage Explorer", command=window.open_storage_explorer)
        tools_menu.add_command(label="Open APK Laboratory", command=window.open_apk_laboratory)
        tools_menu.add_command(label="Open Findings", command=window.open_findings)
        tools_menu.add_command(label="Open Report Builder", command=window.open_report_builder)
        tools_menu.add_command(label="Open Plugin Manager", command=window.open_plugin_manager)
        tools_menu.add_command(label="New Assessment Case", command=window.new_assessment_case)
        self.tools_menu=tools_menu;self.plugin_start=tools_menu.index("end")+1;self.refresh_plugin_actions()
        registry=getattr(window,"plugin_registry",None);self.unsubscribe=registry.subscribe(lambda _items:window.after(0,self.refresh_plugin_actions)) if registry else None
        menu.add_cascade(label="Tools", menu=tools_menu)

        addons_menu=tk.Menu(menu,tearoff=False,font=MENU_FONT)
        addons_menu.add_command(label="Open Add-ons Center…",command=window.open_addons_center)
        addons_menu.add_command(label="Official Addon Catalog…",command=window.open_addons_center)
        addons_menu.add_command(label="Manage Installed Addons…",command=window.open_plugin_manager)
        addons_menu.add_command(label="Addon Diagnostics…",command=window.open_plugin_manager)
        addons_menu.add_separator();self.loaded_menu=tk.Menu(addons_menu,tearoff=False,font=MENU_FONT);addons_menu.add_cascade(label="Open Loaded Addon",menu=self.loaded_menu)
        addons_menu.add_separator();addons_menu.add_command(label="Unload All Addons",command=window.unload_all_addons)
        menu.add_cascade(label="Addons",menu=addons_menu);self.addons_menu=addons_menu;self.refresh_loaded_addons()
        manager=getattr(window,"plugin_manager",None);self.manager_unsubscribe=manager.subscribe(lambda _event,_pid:window.after(0,self.refresh_loaded_addons)) if manager else None

        help_menu = tk.Menu(menu, tearoff=False, font=MENU_FONT)
        help_menu.add_command(label="Contextual Help", command=window.open_current_help)
        help_menu.add_command(
            label="Guided Instrumentation Setup",
            command=window.open_guided_setup,
        )
        help_menu.add_command(
            label="Learning Center",
            command=window.open_learning_center,
        )
        help_menu.add_command(
            label="Explain This Screen",
            command=window.explain_current_screen,
        )
        help_menu.add_command(
            label="Glossary",
            command=lambda: window.open_context_help("learning-center").tabs.set("Glossary"),
        )
        help_menu.add_command(
            label="Advanced Command Reference",
            command=window.open_cheat_sheet,
        )
        menu.add_cascade(label="Help", menu=help_menu)

        about_menu = tk.Menu(menu, tearoff=False, font=MENU_FONT)
        about_menu.add_command(label=f"About {METADATA.application_name}", command=self.about_box)
        menu.add_cascade(label="About", menu=about_menu)

        window.config(menu=menu)

    def refresh_plugin_actions(self):
        end=self.tools_menu.index("end")
        if end is not None and end>=self.plugin_start:self.tools_menu.delete(self.plugin_start,"end")
        actions=getattr(getattr(self.window,"plugin_registry",None),"list",lambda _type:())("menu-action")
        if actions:self.tools_menu.add_separator()
        for action in actions:
            target=action.metadata.get("target","");self.tools_menu.add_command(label=action.title,command=lambda value=target:self.window.open_plugin_contribution(value))

    def refresh_loaded_addons(self):
        self.loaded_menu.delete(0,"end");items=getattr(getattr(self.window,"plugin_registry",None),"list",lambda _type:())("pentest-panel")
        if not items:self.loaded_menu.add_command(label="No loaded addons",state="disabled");return
        for item in items:self.loaded_menu.add_command(label=item.title,command=lambda cid=item.contribution_id:self.window.open_addon_window(cid))

    def about_box(self):

        messagebox.showinfo(
            f"About {METADATA.application_name}",
            f"{METADATA.display_version}\n\n"
            f"{METADATA.descriptor}\n\n"
            f"{METADATA.build_details}\n\n"
            "Legacy sus-adb CLI and local storage remain compatible.\n\n"
            "Created by DoctorSUS & ChatGPT"
        )
