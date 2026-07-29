import customtkinter as ctk
from app.core.app_metadata import METADATA
from app.gui.read_only_text import ReadOnlyTextView
class EnvironmentDiagnosticsWindow(ctk.CTkToplevel):
    def __init__(self,parent,theme,records,startup_report=""):
        super().__init__(parent);self.title(f"{METADATA.application_name} Diagnostics");self.geometry("860x640");self.transient(parent);self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(0,weight=1);self.tabs=ctk.CTkTabview(self,fg_color=theme["panel"],segmented_button_fg_color=theme["panel_alt"],segmented_button_selected_color=theme["red"],segmented_button_selected_hover_color=theme["red_hover"],segmented_button_unselected_color=theme["panel_alt"],segmented_button_unselected_hover_color=theme["gold_dark"],text_color=theme["text"]);self.tabs.grid(row=0,column=0,sticky="nsew",padx=10,pady=10)
        build=self.tabs.add("Build");environment=self.tabs.add("Environment");startup=self.tabs.add("Startup");
        for page in (build,environment,startup):page.grid_columnconfigure(0,weight=1);page.grid_rowconfigure(0,weight=1)
        build_view=ReadOnlyTextView(build,fg_color=theme["terminal_bg"],text_color=theme["text"],wrap="word",initial_text=f"{METADATA.application_name}\n{METADATA.build_details}\n\nPlatform: {METADATA.platform_name} {METADATA.architecture}\nPython: {METADATA.python_version}\n\nBuild metadata is local and contains no telemetry.");build_view.grid(row=0,column=0,sticky="nsew",padx=6,pady=6);self.build_view=build_view
        view=ReadOnlyTextView(environment,fg_color=theme["terminal_bg"],text_color=theme["text"],wrap="word",initial_text="\n\n".join(f"{'READY' if r.available else 'MISSING'} · {r.name} · {'Required' if r.required else 'Optional'}\n{r.version or r.path}\n{r.guidance}" for r in records));view.grid(row=0,column=0,sticky="nsew",padx=6,pady=6)
        self.startup_view=ReadOnlyTextView(startup,fg_color=theme["terminal_bg"],text_color=theme["text"],wrap="word",initial_text=startup_report or "Startup timing becomes available after the responsive Console shell is created.");self.startup_view.grid(row=0,column=0,sticky="nsew",padx=6,pady=6)
