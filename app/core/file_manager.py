"""
File utilities.
"""

from tkinter import filedialog


class FileManager:

    @staticmethod
    def save_console(text):

        filename = filedialog.asksaveasfilename(

            defaultextension=".txt",

            filetypes=[

                ("Text Files","*.txt"),

                ("Log Files","*.log"),

                ("All Files","*.*")

            ]

        )

        if not filename:

            return

        with open(

            filename,

            "w",

            encoding="utf-8"

        ) as f:

            f.write(text)