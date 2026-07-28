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
        from app.core.script_operation import ScriptOperation
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
        panel.workspace.set("Editor")
        root.update_idletasks()
        assert panel.editor.winfo_ismapped()
        assert panel.editor.winfo_height() > 1
        assert not any(
            button.winfo_manager()
            for button in panel.operation_action_buttons
        )
        panel.select_descriptor(created.descriptor)
        readonly_views = (
            panel.library_details,
            panel.operation_details,
            panel.rpc_result,
            panel.message_view,
            panel.profile_view,
        )
        assert all(view.read_only for view in readonly_views)

        def generate(widget, sequence, **kwargs):
            widget.focus_force()
            root.update()
            widget.event_generate(sequence, **kwargs)
            root.update()

        details = panel.library_details
        details_inner = details._textbox
        details_before = details.get("1.0", "end-1c")
        for sequence, kwargs in (
            ("<KeyPress>", {"keysym": "x"}),
            ("<BackSpace>", {}),
            ("<Delete>", {}),
            ("<<Cut>>", {}),
            ("<<Paste>>", {}),
            ("<Button-2>", {"x": 5, "y": 5}),
        ):
            generate(details_inner, sequence, **kwargs)
            assert details.get("1.0", "end-1c") == details_before
        generate(details_inner, "<KeyPress>", keysym="a", state=0x0004)
        assert details_inner.tag_ranges("sel")
        generate(details_inner, "<KeyPress>", keysym="c", state=0x0004)
        assert root.clipboard_get() == details_before
        details.replace("programmatic replacement")
        assert details.get("1.0", "end-1c") == "programmatic replacement"
        assert details.read_only
        try:
            details._mutate(
                lambda: (_ for _ in ()).throw(RuntimeError("fixture"))
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("failed mutation fixture did not raise")
        assert details.read_only
        panel._render_details()
        assert details.get("1.0", "end-1c") == details_before
        panel.editor.tag_remove("sel", "1.0", "end")
        generate(details_inner, "<KeyPress>", keysym="a", state=0x0004)
        assert details_inner.tag_ranges("sel")
        assert not panel.editor.tag_ranges("sel")
        panel.workspace.set("Editor")
        editor_before = panel.editor.get("1.0", "end-1c")
        generate(panel.editor._textbox, "<Control-a>")
        assert panel.editor._textbox.tag_ranges("sel")
        generate(panel.editor._textbox, "<Control-c>")
        copied_source = root.clipboard_get()
        generate(panel.editor._textbox, "<Control-x>")
        assert panel.editor.get("1.0", "end-1c") == ""
        generate(panel.editor._textbox, "<Control-v>")
        assert panel.editor.get("1.0", "end-1c") == copied_source
        panel.editor.insert("end", "\n// editable fixture")
        assert panel.editor.get("1.0", "end-1c") != editor_before
        panel.editor.edit_modified(True)
        panel._editor_modified(None)
        assert panel.editor_dirty

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
        assert panel.suggestions_button.winfo_manager()
        assert not panel.jump_line_button.winfo_manager()

        panel.operation_model.begin("Fixture failure", stage="Compiling")
        panel.operation_model.fail(
            "Compilation failed.",
            technical_details="Line 3: fixture syntax error\nfixture trace",
        )
        panel._render_operation()
        assert panel.jump_line_button.winfo_manager()
        assert panel.copy_error_button.winfo_manager()
        assert panel.technical_button.winfo_manager()
        panel.toggle_technical_details()
        root.update_idletasks()
        assert panel.operation_details.winfo_ismapped()
        assert panel.operation_details.read_only
        panel.toggle_technical_details()
        root.update_idletasks()
        assert not panel.operation_details.winfo_ismapped()
        panel.operation_model.current = ScriptOperation(message="Ready.")
        panel.operation_model.saved(False)
        panel._validation_result = None
        panel.dismiss_validation()
        panel._render_operation()
        assert not any(
            button.winfo_manager()
            for button in panel.operation_action_buttons
        )

        panel.open_selected()
        clean_source = panel.editor.get("1.0", "end-1c")
        panel.editor.mark_set("insert", "2.2")
        clean_cursor = panel.editor.index("insert")
        assert not panel.editor_dirty

        second = library.create(
            "second fixture",
            "'use strict';\nsend('second');\n",
            kind=ScriptKind.FRIDA,
        )
        assert second.ok
        panel.refresh_library()
        panel.select_descriptor(second.descriptor)
        assert "second" in panel.editor.get("1.0", "end-1c")
        panel.select_descriptor(created.descriptor)
        assert panel.editor.get("1.0", "end-1c") == clean_source
        panel.editor.insert(
            "end",
            "\n// save fixture "
            + "x" * 300
            + "\n"
            + "\n".join(f"// scroll line {index}" for index in range(120)),
        )
        panel.editor.edit_modified(True)
        panel._editor_modified(None)
        assert panel.editor_dirty
        panel.save_editor()
        assert not panel.editor_dirty
        assert panel.unsaved_label.cget("text") in (
            "Saved", "Reload Required"
        )
        clean_source = panel.editor.get("1.0", "end-1c")
        panel.editor.mark_set("insert", "2.2")
        clean_cursor = panel.editor.index("insert")

        measurements = []
        target_heights = {
            (1100, 700): 140,
            (1200, 760): 180,
            (1400, 860): 260,
            (1600, 900): 300,
        }
        for scale in (1.0, 1.25, 1.5):
            ctk.set_widget_scaling(scale)
            root.minsize(1, 1)
            root.maxsize(root.winfo_screenwidth(), root.winfo_screenheight())
            root.update()
            time.sleep(0.03)
            root.update()
            root.deiconify()
            root.update_idletasks()
            for width, height in (
                (1100, 700), (1200, 760), (1400, 860), (1600, 900)
            ):
                root.geometry(f"{width}x{height}+0+0")
                root.deiconify()
                panel.workspace.set("Library")
                panel.workspace.set("Editor")
                panel.operation_model.current = ScriptOperation(
                    message="Ready."
                )
                panel.operation_model.saved(False)
                panel._validation_result = None
                panel.dismiss_validation()
                panel._render_operation()
                panel.absolute_path_label.grid_remove()
                root.update_idletasks()
                actual_window = (root.winfo_width(), root.winfo_height())
                editor_top = panel.editor.winfo_rooty() - root.winfo_rooty()
                editor_height = panel.editor.winfo_height()
                editor_bottom = editor_top + editor_height
                status_height = panel.operation_notice.winfo_height()
                path_height = panel.path_bar.winfo_height()
                bottom_height = panel.bottom_actions.winfo_height()
                final_button = panel.editor_action_buttons[-1]
                final_bounds = (
                    final_button.winfo_rootx() - root.winfo_rootx(),
                    final_button.winfo_rooty() - root.winfo_rooty(),
                    final_button.winfo_width(),
                    final_button.winfo_height(),
                )
                assert editor_height >= (
                    target_heights[(width, height)]
                    if scale == 1.0 else 90
                ), (
                    f"editor height {editor_height} at "
                    f"{width}x{height}@{scale}"
                )
                assert all(
                    button.winfo_ismapped()
                    for button in panel.path_action_buttons
                ), (
                    width,
                    height,
                    scale,
                    [
                        (
                            button.cget("text"),
                            button.winfo_manager(),
                            button.winfo_ismapped(),
                        )
                        for button in panel.path_action_buttons
                    ],
                    (
                        panel.path_bar.winfo_ismapped(),
                        panel.path_actions.winfo_ismapped(),
                        panel.editor_frame.winfo_ismapped(),
                        panel.workspace.get(),
                        actual_window,
                    ),
                )
                assert all(
                    button.winfo_ismapped()
                    for button in panel.editor_action_buttons
                )
                assert not any(
                    button.winfo_manager()
                    for button in panel.operation_action_buttons
                )
                assert not panel.operation_progress.winfo_ismapped()
                assert (
                    final_bounds[0] + final_bounds[2]
                    <= actual_window[0] + 2
                )
                assert (
                    final_bounds[1] + final_bounds[3]
                    <= actual_window[1] + 2
                )
                for button in (
                    *panel.path_action_buttons,
                    *panel.editor_action_buttons,
                ):
                    left = button.winfo_rootx() - root.winfo_rootx()
                    top = button.winfo_rooty() - root.winfo_rooty()
                    assert left >= 0 and top >= 0
                    assert (
                        left + button.winfo_width()
                        <= actual_window[0] + 2
                    )
                    assert (
                        top + button.winfo_height()
                        <= actual_window[1] + 2
                    )
                source_before = panel.editor.get("1.0", "end-1c")
                cursor_before = panel.editor.index("insert")
                dirty_before = panel.editor_dirty
                root.geometry(f"{width + 7}x{height + 3}+0+0")
                root.deiconify()
                root.update_idletasks()
                root.geometry(f"{width}x{height}+0+0")
                root.deiconify()
                root.update_idletasks()
                assert panel.editor.get("1.0", "end-1c") == source_before
                assert panel.editor.index("insert") == cursor_before
                assert panel.editor_dirty == dirty_before

                panel.operation_model.begin(
                    "Fixture failure", stage="Compiling"
                )
                panel._render_operation()
                root.update_idletasks()
                assert panel.operation_progress.winfo_ismapped(), (
                    width,
                    height,
                    scale,
                    panel.operation_progress.winfo_manager(),
                    panel.operation_notice.winfo_ismapped(),
                    panel.editor_frame.winfo_ismapped(),
                )
                panel.operation_model.fail(
                    "Compilation failed.",
                    technical_details=(
                        "Line 3: fixture syntax error\n"
                        + "\n".join(f"trace {index}" for index in range(30))
                    ),
                )
                panel._render_operation()
                assert not panel.operation_progress.winfo_ismapped()
                panel.toggle_technical_details()
                root.update_idletasks()
                expanded_status_height = panel.operation_notice.winfo_height()
                expanded_editor_height = panel.editor.winfo_height()
                assert expanded_editor_height >= 50, (
                    width, height, scale, expanded_editor_height
                )
                collapse_left = (
                    panel.collapse_details_button.winfo_rootx()
                    - root.winfo_rootx()
                )
                collapse_top = (
                    panel.collapse_details_button.winfo_rooty()
                    - root.winfo_rooty()
                )
                assert collapse_left >= 0 and collapse_top >= 0
                assert (
                    collapse_left
                    + panel.collapse_details_button.winfo_width()
                    <= actual_window[0] + 2
                )
                panel.toggle_technical_details()
                root.update_idletasks()
                assert panel.editor.get("1.0", "end-1c") == source_before
                assert panel.editor.index("insert") == cursor_before

                measurements.append(
                    {
                        "case": (
                            f"{width}x{height}@{int(scale * 100)}%"
                        ),
                        "window": actual_window,
                        "tab": panel.tabs["Editor"].winfo_height(),
                        "editor_top": editor_top,
                        "editor_bottom": editor_bottom,
                        "editor": editor_height,
                        "path": path_height,
                        "status": status_height,
                        "expanded_status": expanded_status_height,
                        "expanded_editor": expanded_editor_height,
                        "actions": bottom_height,
                        "final_button": final_bounds,
                        "footer": root.winfo_height(),
                    }
                )
                for tab in panel.tabs:
                    panel.workspace.set(tab)
                    root.update_idletasks()
                    buttons = [
                        widget for widget in descendants(panel)
                        if isinstance(widget, ctk.CTkButton)
                        and widget.winfo_ismapped()
                    ]
                    visible_audited_views = [
                        view for view in (*readonly_views, panel.editor)
                        if view.winfo_ismapped()
                    ]
                    clipped = [
                        (
                            widget.__class__.__name__,
                            widget.winfo_rootx(),
                            widget.winfo_rooty(),
                            widget.winfo_width(),
                            widget.winfo_height(),
                        )
                        for widget in visible_audited_views
                        if (
                            widget.winfo_rootx() + widget.winfo_width()
                            > root.winfo_rootx() + root.winfo_width() + 2
                            or widget.winfo_rooty() + widget.winfo_height()
                            > root.winfo_rooty() + root.winfo_height() + 2
                        )
                    ]
                    assert not clipped, (
                        f"clipped text surfaces at "
                        f"{width}x{height}@{scale}: {clipped}"
                    )
                    assert all(
                        not str(widget.cget("fg_color")).casefold().startswith(
                            "blue"
                        )
                        for widget in buttons
                    )
                panel.workspace.set("Editor")
                root.update_idletasks()
                assert panel.editor.get("1.0", "end-1c") == clean_source
                assert panel.editor._textbox.cget("wrap") == "none"
                long_index = panel.editor.search("x" * 50, "1.0")
                assert long_index
                panel.editor.see(f"{long_index.split('.')[0]}.end")
                root.update_idletasks()
                panel.editor.xview_moveto(0)
                horizontal_before = panel.editor.xview()
                panel.editor.xview_scroll(1, "pages")
                assert panel.editor.xview() != horizontal_before, (
                    horizontal_before,
                    panel.editor.xview(),
                    panel.editor.winfo_width(),
                    len(max(clean_source.splitlines(), key=len)),
                )
                panel.editor.yview_moveto(0)
                vertical_before = panel.editor.yview()
                panel.editor.yview_scroll(1, "pages")
                assert panel.editor.yview() != vertical_before
        assert panel.editor.index("insert") == clean_cursor
        assert not panel.editor_dirty
        layout_bindings = panel._layout_bindings.count
        binding_counts = tuple(view.binding_count for view in readonly_views)
        root.destroy()
        assert all(view.binding_count == 0 for view in readonly_views)
        assert panel._layout_bindings.count == 0
    print(
        "script-studio-smoke=PASS "
        f"measurements={measurements} bindings={binding_counts}->0 "
        f"layout-bindings={layout_bindings}->0 "
        "read-only-details-results-messages-profiles=PASS "
        "editor-input-dirty-state=PASS "
        "inline-status-errors-advisories-paths-messages=PASS fake-only=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
