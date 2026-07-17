import customtkinter as ctk


class CheatSheetWindow(ctk.CTkToplevel):

    def __init__(self, parent, theme):
        super().__init__(parent)

        self.theme = theme

        self.title("SUS-ADB Cheat Sheet")

        self.geometry("420x540")
        self.resizable(False, False)

        self.configure(fg_color=theme["bg"])

        self.after(100, self.center_window)

        self.grab_set()

        title = ctk.CTkLabel(
            self,
            text="⚔ SUS-ADB COMMAND CHEAT SHEET ⚔",
            font=("Cinzel", 22, "bold"),      # smaller than title_font
            text_color=theme["gold"],
            anchor="center",
            justify="center"
        )
        title.pack(fill="x", padx=20, pady=(20, 15))

        console = ctk.CTkTextbox(
            self,
            fg_color=theme["terminal_bg"],
            text_color=theme["terminal_text"],
            font=theme["terminal_font"],
            border_width=1
        )
        console.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        commands = """
=== SUS-ADB COMMANDS ===

help
clear
exit


=== ADB ===

adb devices
adb shell
adb reboot
adb reboot recovery
adb reboot bootloader
adb install app.apk
adb uninstall com.example.app
adb push local_file /sdcard/
adb pull /sdcard/file.txt


=== FRIDA ===

frida-ps -U
frida-ps -Uai
frida -U -n "AppName"
frida -U -f com.example.app


=== OBJECTION ===

objection -g com.example.app explore
objection -S socket -n AppName start


=== TIPS ===

• Use the command bar at the top.

• Every command appears in the terminal.

• Type clear to clear the console.

• Type help for built-in commands.

• The prompt is:

sus-adb >

⚔ Hack the Castle ⚔
"""

        console.insert("1.0", commands)
        console.configure(state="disabled")

    def center_window(self):

        self.update_idletasks()

        width = self.winfo_width()
        height = self.winfo_height()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")