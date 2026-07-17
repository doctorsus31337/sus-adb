import customtkinter as ctk


class CheatSheetWindow(ctk.CTkToplevel):
    def __init__(self, parent, theme):
        super().__init__(parent)

        self.title("SUS-ADB Cheat Sheet")
        self.geometry("650x700")
        self.configure(fg_color=theme["bg"])

        self.grab_set()

        title = ctk.CTkLabel(
            self,
            text="⚔ SUS-ADB COMMAND CHEAT SHEET ⚔",
            font=theme["title_font"],
            text_color=theme["gold"]
        )
        title.pack(pady=(20, 15))

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

- Use the terminal bar at the top to execute commands.
- Output appears in the built-in console below.
- All commands run in a background thread.
- The console prompt is: sus-adb >

⚔ Hack the Castle ⚔
"""

        console.insert("1.0", commands)
        console.configure(state="disabled")