"""Headless fake-only Script Studio interaction and layout smoke."""

from __future__ import annotations

import os
import queue
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix="script studio library ") as directory:
        os.environ["XDG_CONFIG_HOME"] = directory
        import customtkinter as ctk

        from app.core.device import Device
        from app.core.frida_runtime_manager import RuntimeResult, RuntimeState
        from app.core.frida_target import FridaTarget, TargetType
        from app.core.script_descriptor import ScriptKind, TrustState
        from app.core.script_event import ScriptEvent, ScriptEventType
        from app.core.script_library import ScriptLibrary
        from app.core.script_validator import ScriptValidator
        from app.gui.script_studio_panel import ScriptStudioPanel
        from app.gui.theme import get_theme

        class Availability:
            ok = True
            value = {"version": "fixture"}
            error = None

        class Adapter:
            @staticmethod
            def availability():
                return Availability()

        class Runtime:
            def __init__(self):
                self.adapter = Adapter()
                self.state = RuntimeState.ACTIVE
                self.session = None
                self.spawned_pid = None
                self.last_diagnosis = None
                self.version_warning = None
                self.loaded = {}
                self.event_callback = None
                self.fail_reload = False

            def list_loaded(self):
                return tuple(self.loaded.values())

            def load_script(self, descriptor, **_confirmations):
                if descriptor.script_id in self.loaded:
                    return RuntimeResult(
                        True,
                        self.loaded[descriptor.script_id],
                        warning="The script is already loaded.",
                    )
                record = SimpleNamespace(
                    descriptor=descriptor,
                    state="active",
                    rpc_exports=(),
                )
                self.loaded[descriptor.script_id] = record
                return RuntimeResult(True, record)

            def reload_script(self, script_id, **_confirmations):
                if self.fail_reload:
                    return RuntimeResult(
                        False,
                        error="JavaScript compilation failed\n"
                        "Line 47: unexpected token `}`",
                    )
                return RuntimeResult(True, self.loaded.get(script_id))

            def unload_script(self, script_id):
                self.loaded.pop(script_id, None)
                return RuntimeResult(True)

            def attach(self, _serial, _target):
                return RuntimeResult(True)

            def spawn(self, _serial, _target):
                return RuntimeResult(True)

            def resume(self):
                return RuntimeResult(True)

            def detach(self):
                self.session = None
                return RuntimeResult(True)

            def post(self, _script_id, _message):
                return RuntimeResult(True)

            def list_rpc_exports(self, _script_id):
                return RuntimeResult(True, ())

            def call_rpc(self, _script_id, _name, _args):
                return RuntimeResult(True, "fixture")

            def unload_all(self):
                self.loaded.clear()
                return (RuntimeResult(True),)

            def reload_all(self, **_confirmations):
                return (RuntimeResult(True),)

            def load_multiple(self, _descriptors, **_confirmations):
                return (RuntimeResult(True),)

            def device_disconnected(self):
                return RuntimeResult(True)

        library = ScriptLibrary(Path(directory) / "library with spaces")
        created = library.create(
            "my script",
            "\n".join(
                (
                    "'use strict';",
                    "Java.perform(function () {",
                    "  send('ready');",
                    "});",
                )
            ),
            kind=ScriptKind.FRIDA,
        )
        assert created.ok
        root = ctk.CTk()
        root.geometry("1200x760+0+0")
        opened = []
        launched = []
        settings = []
        runtime = Runtime()
        ui_queue = queue.Queue()
        panel = ScriptStudioPanel(
            root,
            get_theme(),
            library,
            runtime,
            ScriptValidator(),
            lambda _message: None,
            confirm_callback=lambda _title, _text: True,
            show_advisories=False,
            setting_callback=settings.append,
            launch_session_callback=launched.append,
            open_folder_callback=lambda path: opened.append(path) or True,
            ui_dispatch=lambda callback, *args: ui_queue.put((callback, args)),
        )
        panel.pack(fill="both", expand=True)
        panel.set_selected_device(Device("SERIAL", "device", model="Fixture"))
        panel.set_selected_target(
            FridaTarget(
                "Fixture App",
                "org.example.fixture",
                42,
                TargetType.APPLICATION,
                True,
            )
        )
        runtime.session = object()
        panel.select_descriptor(created.descriptor)

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def settle():
            deadline = time.monotonic() + 5
            while (
                panel.operation_model.busy
                and time.monotonic() < deadline
            ):
                while not ui_queue.empty():
                    callback, args = ui_queue.get_nowait()
                    callback(*args)
                root.update()
                time.sleep(0.005)
            while not ui_queue.empty():
                callback, args = ui_queue.get_nowait()
                callback(*args)
            root.update()
            assert not panel.operation_model.busy

        panel.validate_selected()
        assert "compatibility suggestion" in panel.validation_message.cget("text")
        assert "cannot prove third-party" not in panel.validation_message.cget("text")
        panel.show_compatibility_suggestions()
        assert "Java.available" in panel.validation_message.cget("text")
        panel.load_selected()
        settle()
        assert panel.unsaved_label.cget("text") == "Loaded"
        assert panel.operation_message.cget("text") == "Script loaded successfully."
        panel.editor.insert("end", "\n// edit")
        panel.editor.edit_modified(True)
        panel._editor_modified(None)
        assert panel.unsaved_label.cget("text") == "Reload Required"
        panel.load_selected()
        assert "Use Reload" in panel.operation_message.cget("text")
        runtime.fail_reload = True
        panel.reload_selected()
        settle()
        assert panel.operation_model.current.error_line == 47
        assert panel.unsaved_label.cget("text") == "Error"
        panel._accept_event(
            ScriptEvent(
                ScriptEventType.ERROR,
                "runtime failed",
                script_name="my script",
                source_line=2,
                stack_trace="fixture trace",
            )
        )
        assert panel.workspace.get() == "Messages"
        assert panel.operation_model.current.error_line == 2
        panel.copy_script_path()
        assert "library with spaces" in root.clipboard_get()
        panel.open_containing_folder()
        panel.launch_in_frida_repl()
        assert opened and launched
        panel.show_advisories.set(True)
        panel._advisory_setting_changed()
        assert settings[-1] is True
        assert "cannot prove third-party" not in panel.validation_message.cget("text")
        panel.selected = replace(panel.selected, trust=TrustState.UNTRUSTED)
        panel._show_validation(
            panel.validator.validate(
                panel.selected, panel.editor.get("1.0", "end-1c")
            )
        )
        assert "cannot prove third-party" in panel.validation_message.cget("text")

        for width, height in ((1200, 760), (1400, 860)):
            root.geometry(f"{width}x{height}+0+0")
            for tab in panel.tabs:
                panel.workspace.set(tab)
                root.update_idletasks()
                buttons = [
                    widget for widget in descendants(panel)
                    if isinstance(widget, ctk.CTkButton) and widget.winfo_ismapped()
                ]
                assert all(
                    widget.winfo_rootx() + widget.winfo_width()
                    <= root.winfo_rootx() + root.winfo_width() + 2
                    and widget.winfo_rooty() + widget.winfo_height()
                    <= root.winfo_rooty() + root.winfo_height() + 2
                    for widget in buttons
                )
                assert all(
                    not str(widget.cget("fg_color")).casefold().startswith("blue")
                    for widget in buttons
                )
        root.destroy()
    print(
        "script-studio-smoke=PASS sizes=1200x760,1400x860 "
        "inline-status-errors-advisories-paths-messages=PASS fake-only=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
