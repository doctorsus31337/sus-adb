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
        from app.gui.main_window import SusADBWindow

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
        opened = []
        launched = []
        settings = []
        runtime = Runtime()
        ui_queue = queue.Queue()
        root = SusADBWindow()
        root._deferred_started = True
        root.script_library = library
        root.frida_runtime = runtime
        root.script_validator = ScriptValidator()
        root.app_config.setdefault("script_studio", {})[
            "show_static_analysis_advisories"
        ] = False
        root._set_script_advisories = settings.append
        root.open_script_session = launched.append
        root.open_local_directory = lambda path: opened.append(path) or True
        root.call_on_ui = (
            lambda callback, *args: ui_queue.put((callback, args))
        )
        panel = root.navigate_workspace("Scripts")
        panel.confirm = lambda _title, _text: True
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
        panel._select_workspace("Editor")
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
        panel._select_workspace("Editor")
        editor_before = panel.editor.get("1.0", "end-1c")
        assert panel.editor._textbox.bind("<Control-a>")
        assert panel._select_editor_all() == "break"
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

        def button_text_fits(button):
            font = getattr(button, "_font", None)
            text = str(button.cget("text"))
            if not text or font is None or not hasattr(font, "measure"):
                return True
            required = max(
                font.measure(line) for line in text.splitlines()
            ) + 18
            return required <= button.winfo_width()

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

        layout_bindings = panel._layout_bindings.count
        binding_counts = tuple(view.binding_count for view in readonly_views)
        root.shutdown()
        assert all(view.binding_count == 0 for view in readonly_views)
        assert panel._layout_bindings.count == 0

        measurements = []
        target_heights = {
            (1100, 700): 180,
            (1200, 760): 240,
            (1400, 860): 340,
            (1600, 900): 380,
        }

        def settle_geometry(app, width, height):
            app.geometry(f"{width}x{height}+0+0")
            app.deiconify()
            for _ in range(3):
                app.update()
                app.update_idletasks()
                time.sleep(0.01)

        for scale in (1.0, 1.25, 1.5):
            previous_editor_height = 0
            for width, height in (
                (1100, 700), (1200, 760), (1400, 860), (1600, 900)
            ):
                ctk.set_widget_scaling(scale)
                case_runtime = Runtime()
                case_runtime.state = RuntimeState.IDLE
                case_root = SusADBWindow()
                case_root._deferred_started = True
                settle_geometry(case_root, width, height)
                case_root.script_library = library
                case_root.frida_runtime = case_runtime
                case_root.script_validator = ScriptValidator()
                case_panel = case_root.navigate_workspace("Scripts")
                case_panel.confirm = lambda _title, _text: True
                case_panel._select_workspace("Editor")
                case_panel.select_descriptor(created.descriptor)
                case_panel.editor.insert(
                    "end",
                    "\n// dirty live-layout fixture "
                    + "x" * 300
                    + "\n"
                    + "\n".join(
                        f"// visible source line {index}"
                        for index in range(1, 100)
                    ),
                )
                case_panel.editor.edit_modified(True)
                case_panel._editor_modified(None)
                case_panel.editor.mark_set("insert", "3.5")
                case_panel.editor.tag_add("sel", "3.0", "3.5")
                case_panel._cursor_update()
                case_panel.operation_model.current = ScriptOperation(
                    message="Ready."
                )
                case_panel.operation_model.edited(False)
                case_panel._validation_result = None
                case_panel.dismiss_validation()
                case_panel.absolute_path_label.grid_remove()
                case_panel._render_operation()
                settle_geometry(case_root, width, height)
                case_panel._select_workspace("Editor")
                settle_geometry(case_root, width, height)

                actual_window = (
                    case_root.winfo_width(), case_root.winfo_height()
                )
                editor_top = (
                    case_panel.editor.winfo_rooty()
                    - case_root.winfo_rooty()
                )
                editor_height = case_panel.editor.winfo_height()
                editor_bottom = editor_top + editor_height
                status_top = (
                    case_panel.operation_notice.winfo_rooty()
                    - case_root.winfo_rooty()
                )
                status_height = case_panel.operation_notice.winfo_height()
                bottom_top = (
                    case_panel.bottom_actions.winfo_rooty()
                    - case_root.winfo_rooty()
                )
                bottom_height = case_panel.bottom_actions.winfo_height()
                footer_top = case_root.winfo_height()
                clearance = footer_top - (bottom_top + bottom_height)
                ratio = editor_height / status_height
                inner = case_panel.editor._textbox
                first_line = int(inner.index("@0,0").split(".")[0])
                last_line = int(
                    inner.index(f"@0,{max(0, inner.winfo_height() - 1)}")
                    .split(".")[0]
                )
                visible_lines = max(1, last_line - first_line + 1)

                assert actual_window == (width, height), actual_window
                if scale == 1.0:
                    assert editor_height >= target_heights[(width, height)], (
                        width, height, scale, editor_height,
                        target_heights[(width, height)],
                    )
                assert status_height <= int(48 * scale + 0.5)
                assert ratio >= 4, (width, height, scale, ratio)
                assert editor_height >= 4 * status_height
                assert editor_height > previous_editor_height, (
                    width, height, scale, editor_height,
                    previous_editor_height,
                )
                previous_editor_height = editor_height
                assert visible_lines >= 4
                assert case_panel.editor._textbox.winfo_manager()
                assert case_panel.editor._textbox.winfo_height() > 1
                assert (
                    case_panel.editor._textbox.winfo_rooty()
                    >= case_panel.editor.winfo_rooty()
                )
                assert (
                    case_panel.operation_notice.cget("fg_color")
                    == case_root.theme["panel_alt"]
                )
                assert case_panel.operation_message.cget("text") == "Ready."
                assert case_panel.unsaved_label.cget("text") == "Unsaved"
                assert case_panel.cursor_label.winfo_manager() == "grid"
                assert "Line 3, Column 5" == case_panel.cursor_label.cget("text")
                assert not case_panel.header.winfo_ismapped()
                assert not case_panel.operation_auxiliary.winfo_ismapped()
                assert not case_panel.operation_actions.winfo_ismapped()
                assert not case_panel.operation_details.winfo_ismapped()
                assert not case_panel.operation_progress.winfo_ismapped()
                assert not case_panel.validation_notice.winfo_ismapped()
                assert all(
                    button.winfo_manager() == "grid"
                    for button in case_panel.editor_action_buttons
                )
                assert len(case_panel.editor_action_buttons) == 9
                for button in (
                    *case_panel.path_action_buttons,
                    *case_panel.editor_action_buttons,
                ):
                    assert button_text_fits(button), (
                        width, height, scale, button.cget("text"),
                        button.winfo_width(),
                    )
                    assert not str(
                        button.cget("fg_color")
                    ).casefold().startswith("blue")
                    left = button.winfo_rootx() - case_root.winfo_rootx()
                    top = button.winfo_rooty() - case_root.winfo_rooty()
                    assert left >= 0 and top >= 0
                    assert left + button.winfo_width() <= width + 2, (
                        width, height, scale, button.cget("text"), left,
                        button.winfo_width(), button.grid_info().get("row"),
                        case_panel._get_widget_scaling(),
                        case_panel.editor_frame.winfo_width(),
                        case_panel.editor_frame.winfo_rootx()
                        - case_root.winfo_rootx(),
                    )
                    assert top + button.winfo_height() <= height + 2, (
                        width, height, scale, button.cget("text"), top,
                        button.winfo_height(),
                    )
                assert clearance >= 0

                source_before = case_panel.editor.get("1.0", "end-1c")
                cursor_before = case_panel.editor.index("insert")
                selection_before = tuple(
                    str(value)
                    for value in case_panel.editor.tag_ranges("sel")
                )
                dirty_before = case_panel.editor_dirty
                settle_geometry(case_root, width + 7, height + 3)
                settle_geometry(case_root, width, height)
                assert (
                    case_panel.editor.get("1.0", "end-1c") == source_before
                )
                assert case_panel.editor.index("insert") == cursor_before
                assert tuple(
                    str(value)
                    for value in case_panel.editor.tag_ranges("sel")
                ) == selection_before
                assert case_panel.editor_dirty == dirty_before

                case_panel._select_workspace("Library")
                case_root.update_idletasks()
                assert case_panel.header.winfo_manager() == "grid"
                assert case_root.gothic_header.winfo_manager() == "grid"
                assert case_root.device_dock.winfo_manager() == "grid"
                assert case_root.status_bar.winfo_manager() == "grid"
                case_panel._select_workspace("Editor")
                case_root.update_idletasks()
                assert not case_panel.header.winfo_manager()
                assert not case_root.gothic_header.winfo_manager()
                assert not case_root.device_dock.winfo_manager()
                assert not case_root.status_bar.winfo_manager()
                assert case_panel.editor.winfo_height() >= 4 * status_height

                case_panel.operation_model.begin(
                    "Fixture failure", stage="Compiling"
                )
                case_panel._render_operation()
                case_root.update_idletasks()
                assert case_panel.operation_progress.winfo_manager() == "grid"
                case_panel.operation_model.fail(
                    "Compilation failed.",
                    technical_details=(
                        "Line 3: fixture syntax error\n"
                        + "\n".join(f"trace {index}" for index in range(30))
                    ),
                )
                case_panel._render_operation()
                case_root.update_idletasks()
                assert not case_panel.operation_progress.winfo_ismapped()
                assert case_panel.jump_line_button.winfo_manager() == "grid"
                assert case_panel.copy_error_button.winfo_manager() == "grid"
                assert case_panel.technical_button.winfo_manager() == "grid"
                assert not case_panel.suggestions_button.winfo_ismapped()
                case_panel.toggle_technical_details()
                case_root.update_idletasks()
                expanded_editor = case_panel.editor.winfo_height()
                details_height = case_panel.operation_details.winfo_height()
                assert case_panel.operation_details.winfo_manager() == "grid"
                assert case_panel.operation_details.read_only
                assert expanded_editor >= 50
                assert details_height <= 0.40 * (
                    expanded_editor + details_height
                ) + 2
                case_panel.toggle_technical_details()
                case_panel.operation_model.current = ScriptOperation(
                    message="Ready."
                )
                case_panel.operation_model.edited(False)
                case_panel._render_operation()
                case_root.update_idletasks()
                assert not case_panel.operation_auxiliary.winfo_ismapped()
                assert (
                    case_panel.editor.winfo_height()
                    >= 4 * case_panel.operation_notice.winfo_height()
                )
                assert case_panel.editor.get("1.0", "end-1c") == source_before
                assert case_panel.editor._textbox.cget("state") == "normal"
                assert case_panel.editor._textbox.cget("wrap") == "none"

                case_panel.editor.xview_moveto(0)
                horizontal_before = case_panel.editor.xview()
                case_panel.editor.xview_scroll(1, "pages")
                assert case_panel.editor.xview() != horizontal_before
                case_panel.editor.yview_moveto(0)
                vertical_before = case_panel.editor.yview()
                case_panel.editor.yview_scroll(1, "pages")
                assert case_panel.editor.yview() != vertical_before

                measurements.append(
                    {
                        "case": f"{width}x{height}@{int(scale * 100)}%",
                        "window": actual_window,
                        "editor_y": editor_top,
                        "editor": editor_height,
                        "status_y": status_top,
                        "status": status_height,
                        "ratio": round(ratio, 2),
                        "bottom": bottom_height,
                        "clearance": clearance,
                        "expanded_editor": expanded_editor,
                        "details": details_height,
                        "visible_lines": visible_lines,
                    }
                )
                case_views = (
                    case_panel.library_details,
                    case_panel.operation_details,
                    case_panel.rpc_result,
                    case_panel.message_view,
                    case_panel.profile_view,
                )
                case_layout_bindings = case_panel._layout_bindings.count
                case_root.shutdown()
                assert all(view.binding_count == 0 for view in case_views)
                assert case_panel._layout_bindings.count == 0
                assert case_layout_bindings == layout_bindings
        ctk.set_widget_scaling(1.0)
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
