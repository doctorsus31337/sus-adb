"""
Application menu bar.
"""

import tkinter as tk
from tkinter import filedialog, messagebox


class MenuBar:

    def __init__(self, window):

        self.window = window

        self.menu = tk.Menu(window)

        #
        # File
        #

        file_menu = tk.Menu(self.menu, tearoff=0)

        file_menu.add_command(
            label="Save Console",
            command=self.window.save_console
        )

        file_menu.add_separator()

        file_menu.add_command(
            label="Exit",
            command=self.window.quit
        )

        self.menu.add_cascade(
            label="File",
            menu=file_menu
        )

        #
        # Settings
        #

        settings = tk.Menu(self.menu, tearoff=0)

        settings.add_command(
            label="Preferences (Coming Soon)"
        )

        self.menu.add_cascade(
            label="Settings",
            menu=settings
        )

        #
        # Tools
        #

        tools = tk.Menu(self.menu, tearoff=0)

        tools.add_command(
            label="Refresh Devices",
            command=self.window.refresh_devices
        )

        tools.add_command(
            label="Clear Console",
            command=self.window.clear_console
        )

        self.menu.add_cascade(
            label="Tools",
            menu=tools
        )

        #
        # About
        #

        about = tk.Menu(self.menu, tearoff=0)

        about.add_command(
            label="About SUS-ADB",
            command=self.about_box
        )

        self.menu.add_cascade(
            label="About",
            menu=about
        )

        window.config(menu=self.menu)


    def about_box(self):

        messagebox.showinfo(

            "About",

            "SUS-ADB Companion\n\n"

            "Cross-platform Android companion\n"

            "Built with Python + CustomTkinter\n\n"

            "Created by DoctorSUS & ChatGPT ❤️"

        )