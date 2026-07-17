import tkinter as tk
from tkinter import messagebox

tk.Menu(root, tearoff=False, font=MENU_FONT)


class MenuBar:

    def __init__(self, window):

        self.window = window

        menu = tk.Menu(window)

        file_menu = tk.Menu(menu, tearoff=False, font=FONT)
        file_menu.add_command(label="Save Console", command=window.save_console)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=window.quit)
        menu.add_cascade(label="File", menu=file_menu)

        settings_menu = tk.Menu(menu, tearoff=False, font=FONT)
        settings_menu.add_command(label="Preferences (Coming Soon)")
        menu.add_cascade(label="Settings", menu=settings_menu)

        tools_menu = tk.Menu(menu, tearoff=False, font=FONT)
        tools_menu.add_command(label="Refresh Devices", command=window.refresh_devices)
        tools_menu.add_command(label="Clear Console", command=window.clear_console)
        menu.add_cascade(label="Tools", menu=tools_menu)

        about_menu = tk.Menu(menu, tearoff=False, font=FONT)
        about_menu.add_command(label="About SUS-ADB", command=self.about_box)
        menu.add_cascade(label="About", menu=about_menu)

        window.config(menu=menu)

    def about_box(self):

        messagebox.showinfo(
            "About SUS-ADB",
            "SUS-ADB Companion\\n\\n"
            "Cross-platform Android reverse engineering companion\\n\\n"
            "Built with Python + CustomTkinter\\n\\n"
            "Created by DoctorSUS & ChatGPT ❤️"
        )