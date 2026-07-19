import tkinter as tk
from tkinter import messagebox

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
        settings_menu.add_command(label="Preferences (Coming Soon)")
        menu.add_cascade(label="Settings", menu=settings_menu)

        tools_menu = tk.Menu(menu, tearoff=False, font=MENU_FONT)
        tools_menu.add_command(label="Refresh Devices", command=window.refresh_devices)
        tools_menu.add_command(label="Clear Console", command=window.clear_console)
        tools_menu.add_separator()
        tools_menu.add_command(label="Enter Pentest Workspace", command=window.enter_pentest_workspace)
        tools_menu.add_command(label="Open ADB Explorer", command=window.open_adb_explorer)
        tools_menu.add_command(label="Open Runtime Explorer", command=window.open_runtime_explorer)
        tools_menu.add_command(label="Open Network Workspace", command=window.open_network_workspace)
        tools_menu.add_command(label="New Assessment Case", command=window.new_assessment_case)
        menu.add_cascade(label="Tools", menu=tools_menu)

        about_menu = tk.Menu(menu, tearoff=False, font=MENU_FONT)
        about_menu.add_command(label="About SUS-ADB", command=self.about_box)
        menu.add_cascade(label="About", menu=about_menu)

        window.config(menu=menu)

    def about_box(self):

        messagebox.showinfo(
            "About SUS-ADB",
            "SUS-ADB\n\n"
            "Cross-platform Android Reverse Engineering Companion\n\n"
            "Created by DoctorSUS & ChatGPT"
        )
