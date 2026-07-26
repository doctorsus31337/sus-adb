"""Local-only GUI acceptance smoke for Plugin Project Wizard v1."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import customtkinter as ctk

from app.core.worker import BackgroundWorker
from app.gui.plugin_project_wizard import PluginProjectWizardWindow
from app.gui.theme import get_theme
from app.plugins.plugin_project import PluginProjectGenerator
from app.plugins.plugin_project_wizard import PluginProjectWizardController


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def assert_no_blue(widget):
    blue = {"blue", "#0000ff", "#1f6aa5", "#144870"}
    for child in (widget, *descendants(widget)):
        for key in ("fg_color", "hover_color", "button_color", "border_color"):
            try:
                value = child.cget(key)
            except Exception:
                continue
            values = value if isinstance(value, (tuple, list)) else (value,)
            assert not any(str(item).casefold() in blue for item in values), (
                child, key, value
            )


def bounds(widget):
    return (
        widget.winfo_rootx(),
        widget.winfo_rooty(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


def pump(root, queue, condition=lambda: True, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while queue:
            callback, args = queue.pop(0)
            callback(*args)
        root.update_idletasks()
        root.update()
        if condition():
            return True
        time.sleep(0.01)
    return False


def main():
    scale = float(os.environ.get("SUS_WIZARD_SCALE", "1.0"))
    ctk.set_widget_scaling(scale)
    root = ctk.CTk()
    root.withdraw()
    errors = []
    root.report_callback_exception = (
        lambda exc, value, traceback: errors.append((exc, value))
    )
    queue = []
    workers = []
    modes = ["guided"]
    factory_calls = []
    handoffs = []

    def factory():
        factory_calls.append(True)
        return PluginProjectGenerator()

    def start(target, callback):
        worker = BackgroundWorker(target, callback=callback)
        workers.append(worker)
        worker.start()
        return worker

    controller = PluginProjectWizardController(factory)
    draft = controller.draft
    draft.project_name = "Wizard GUI Fixture"
    draft.author = "Example Author"
    draft.description = "An inert synthetic GUI fixture."
    controller.set_plugin_id("example-author.wizard-gui-fixture")
    draft.folder_name = "wizard gui fixture"
    draft.contribution_title = "Wizard GUI Fixture"

    with tempfile.TemporaryDirectory(prefix="wizard gui outputs ") as value:
        output = Path(value)
        start_time = time.perf_counter()
        window = PluginProjectWizardWindow(
            root,
            get_theme(),
            controller,
            start_background=start,
            ui_dispatch=lambda callback, *args: queue.append((callback, args)),
            mode_provider=lambda: modes[0],
            workbench_callback=lambda path: handoffs.append(str(path)),
            help_callback=lambda _topic: None,
            choose_folder=lambda: str(output),
            save_zip=lambda **_options: str(output / "starter.zip"),
            save_brief=lambda **_options: str(output / "DEVELOPER_BRIEF.md"),
            confirm=lambda _title, _text: False,
        )
        assert pump(root, queue)
        open_seconds = time.perf_counter() - start_time
        assert factory_calls == []
        assert controller.validation is None

        measurements = []
        for width, height in (
            (900, 680), (980, 720), (1180, 800), (1400, 860)
        ):
            window.geometry(f"{width}x{height}+0+0")
            assert pump(root, queue)
            for step in range(len(window.STEPS)):
                window.current_step = step
                window.render()
                assert pump(root, queue)
                assert (
                    window.status.winfo_rooty() + window.status.winfo_height()
                    <= window.winfo_rooty() + window.winfo_height()
                )
            window.current_step = 3
            window.render()
            assert pump(root, queue)
            canvas = window.viewport.canvas
            region = tuple(
                float(item)
                for item in str(canvas.cget("scrollregion")).split()
            )
            content_height = region[3] - region[1]
            viewport_height = canvas.winfo_height()
            assert content_height > viewport_height
            canvas.yview_moveto(0)
            before = canvas.yview()
            target = next(iter(window.viewport.content.winfo_children()))
            assert window.viewport._wheel(
                SimpleNamespace(widget=target, num=5, delta=0)
            ) == "break"
            assert canvas.yview() != before
            after = canvas.yview()
            outside_before = canvas.yview()
            assert window.viewport._wheel(
                SimpleNamespace(widget=".native.dialog", num=5, delta=0)
            ) is None
            assert canvas.yview() == outside_before
            measurements.append(
                (
                    f"{width}x{height}@{int(scale * 100)}%",
                    bounds(window.viewport),
                    bounds(window.steps),
                    bounds(window.status),
                    round(content_height),
                    viewport_height,
                    before,
                    after,
                    window.viewport.scrollbar.winfo_width(),
                )
            )

        window.geometry("1180x800+0+0")
        window.current_step = 1
        window.render()
        controller.set_plugin_id("susadb.skeleton-module")
        try:
            window._validate_step()
        except ValueError as exc:
            assert "reserved" in str(exc).casefold()
        else:
            raise AssertionError("Reserved identity was not rejected.")
        controller.set_plugin_id("example-author.wizard-gui-fixture")

        controller.set_capabilities(("access-network",))
        window.current_step = 3
        window.render()
        try:
            window._validate_step()
        except ValueError as exc:
            assert "acknowledgment" in str(exc).casefold()
        else:
            raise AssertionError("High-impact acknowledgment was not required.")
        controller.clear_capabilities()

        window.current_step = 5
        window.render()
        assert factory_calls == []
        assert "Not validated" in window.validation_label.cget("text")
        assert window.validate_project()
        assert pump(
            root,
            queue,
            lambda: (
                controller.validated
                and "Compatible starter project"
                in window.validation_label.cget("text")
            ),
        )
        assert factory_calls
        assert "Compatible starter project" in window.validation_label.cget("text")

        modes[0] = "advanced"
        window.apply_mode()
        assert controller.validated
        modes[0] = "guided"
        window.apply_mode()
        assert controller.validated

        window.current_step = 6
        window.render()
        assert window.create_project()
        folder_finished = pump(
            root,
            queue,
            lambda: bool(controller.generated_folder) and window.worker is None,
            seconds=10,
        )
        assert folder_finished, (
            window.status.cget("text"), controller.validated, window.worker,
            len(factory_calls), errors,
        )
        folder = Path(controller.generated_folder)
        assert folder.is_dir()
        assert not window.create_project()  # Existing destination; overwrite declined.
        assert window.build_zip()
        assert pump(
            root,
            queue,
            lambda: bool(controller.generated_zip) and window.worker is None,
        )
        assert Path(controller.generated_zip).is_file()
        assert window.export_brief()
        assert pump(
            root,
            queue,
            lambda: (
                (output / "DEVELOPER_BRIEF.md").is_file()
                and window.worker is None
            ),
        )
        assert (output / "DEVELOPER_BRIEF.md").is_file()
        assert window.open_in_workbench()
        assert handoffs == [controller.generated_folder]

        assert_no_blue(window)
        assert window.viewport.bindings.count == 7
        window.close()
        assert window.viewport.bindings.count == 0
        for worker in workers:
            worker.join(1)
            assert not worker.is_alive()
        assert not queue
        assert not errors, errors
        assert not any(path.name.endswith(".tmp") for path in output.iterdir())
        root.destroy()
        print(
            "plugin-project-wizard-smoke=PASS "
            f"startup={open_seconds:.4f}s measurements={measurements} "
            "steps=7 wheel-touchpad-native-dialog-guard=PASS "
            "reserved-id-high-impact-explicit-validation=PASS "
            "folder-zip-brief-workbench-static-handoff=PASS "
            "guided-advanced-draft-cleanup=PASS"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
