import customtkinter as ctk

from app.gui.gothic_header import GothicHeader
from app.gui.theme import get_theme
from app.gui.device_panel import DevicePanel
from app.gui.command_bar import CommandBar
from app.gui.action_panel import ActionPanel
from app.gui.menu_bar import MenuBar
from app.gui.cheat_sheet_window import CheatSheetWindow
from app.core.device_manager import DeviceManager
from app.core.terminal_manager import TerminalManager
from app.core.file_manager import FileManager
from app.widgets.gothic_button import GothicButton
from app.widgets.gothic_frame import GothicFrame
from app.widgets.gothic_label import GothicLabel
from app.widgets.status_bar import StatusBar
from app.widgets.device_card import DeviceCard
from app.modules.adb import Modules
from app.modules.environment import EnvironmentModule
from app.utils.system_info import SystemInfo
from app.utils.clipboard import ClipboardManager

#------------------Created By DoctorSUS & ChatGPT---------------------------#

class SusADBWindow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.theme = get_theme()

        self.devices = DeviceManager()
        self.terminal = TerminalManager(self.log)
        self.modules = Modules(self.terminal)

        self.title("SUS-ADB Companion")
        self.geometry("1400x860")
        self.minsize(1200, 760)

        self.configure(fg_color=self.theme["bg"])
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        MenuBar(self)

        self.create_widgets()
        self.startup_check()
        self.after(250, self.center_window)



    def startup_check(self):
        info = SystemInfo.get()
        self.log(f"[SYSTEM] {info['platform']} {info['release']}")
        self.log(f"[PYTHON] {info['python']}")
        env = EnvironmentModule.check()
        for tool, found in env.items():
            if found:
                self.log(f"[OK] {tool}")
            else:
                self.log(f"[MISSING] {tool}")


    def center_window(self):

        self.update_idletasks()

        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.geometry(f"+{x}+{y}")


    def create_widgets(self):

        header = GothicHeader(self, self.theme)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 6))

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
            corner_radius=12
        )
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))

        cheat_btn = ctk.CTkButton(
            left,
            text="⚔ Cheat Sheet",
            command=self.open_cheat_sheet,
            fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"],
            text_color=self.theme["text"],
            font=self.theme["button_font"],
            height=44
        )
        cheat_btn.pack(fill="x", padx=10, pady=(15, 32))

        self.device_panel = DevicePanel(
            left,
            self.theme,
            self.refresh_devices,
            self.connect_device
        )
        self.device_panel.pack(fill="x", padx=10, pady=(0, 18))

        self.action_panel = ActionPanel(left, self.execute_command)
        self.action_panel.pack(fill="x", padx=10, pady=(0, 15))

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.command_bar = CommandBar(right, self.execute_command)
        self.command_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.console = ctk.CTkTextbox(
            right,
            fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"],
            font=self.theme["terminal_font"],
            border_width=1
        )
        self.console.grid(row=1, column=0, sticky="nsew")
        self.console.insert("end", "sus-adb > Ready.\n\n")
        
        self.console.bind(
            "<Control-c>",
            lambda e: ClipboardManager.copy(self.console)
)

        self.status_bar = StatusBar(self, self.theme)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))

    def open_cheat_sheet(self):
        CheatSheetWindow(self, self.theme)

    def log(self, text):
        self.console.insert("end", f"{text}\n")
        self.console.see("end")
        self.update_idletasks()

    def execute_command(self, command):

        command = command.strip()

        if not command:
            return

        if command.lower() == "clear":
            self.clear_console()
            self.log("sus-adb > Console cleared.")
            return

        self.terminal.execute(command)

    def refresh_devices(self):

        devices = self.devices.refresh()

        self.device_panel.update_devices(devices)

        count = len(devices)

        self.log(f"[ADB] Found {count} device(s).")

        if count:
            self.status_bar.set_status(adb="Connected", device=f"{count} device(s)")
        else:
            self.status_bar.set_status(adb="No Devices", device="None")

    def connect_device(self):
        self.log("[ADB] Connect feature coming soon.")

    def clear_console(self):
        self.console.delete("1.0", "end")

    def save_console(self):
        FileManager.save_console(self.console.get("1.0", "end"))