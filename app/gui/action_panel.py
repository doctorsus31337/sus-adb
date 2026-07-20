import customtkinter as ctk


from app.widgets.gothic_button import GothicButton
from app.widgets.gothic_frame import GothicFrame
from app.widgets.gothic_label import GothicLabel
from app.widgets.device_card import DeviceCard
from app.widgets.status_bar import StatusBar


class ActionPanel(GothicFrame):

    def __init__(self, parent, run_callback):

        super().__init__(parent)

        self.run = run_callback

        self.configure(fg_color="#16110a")

        title = ctk.CTkLabel(
            self,
            text="Quick Tools",
            font=("Segoe UI", 18, "bold"),
            text_color="#d4af37"
        )
        title.pack(pady=(10, 5))

        self._section("ADB")
        self._button("Devices", "adb devices")
        self._button("Shell", "adb shell")
        self._button("Logcat", "adb logcat")
        self._button("Reboot", "adb reboot")

        self._section("Frida")
        self._button("frida-ps", "frida-ps -H 127.0.0.1:27042")
        self._button("Kill Server", "adb shell su -c pkill frida-server")
        self._button("Start Server", "adb shell su -c /data/local/tmp/frida-server")

        self._section("Objection")
        self._button("Version", "objection version")
        self._button("Patch APK", "objection patchapk --help")

        self._section("Android")
        self._button("Packages", "adb shell pm list packages")
        self._button("Activities", "adb shell dumpsys activity activities")
        self._button("Properties", "adb shell getprop")

    def _section(self, text):

        label = ctk.CTkLabel(
            self,
            text=text,
            font=("Segoe UI", 15, "bold"),
            text_color="#d4af37"
        )
        label.pack(anchor="w", padx=10, pady=(12, 2))

    def _button(self, text, command):

        btn = GothicButton(
            self,
            text=text,
            command=lambda c=command: self.run(c),
            fg_color="#2a2114",
            hover_color="#3a2d1c",
            text_color="#f5deb3"
        )
        btn.pack(fill="x", padx=10, pady=2)
