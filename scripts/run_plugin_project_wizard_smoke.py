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
from app.plugins.plugin_project import (
    PluginProjectGenerator,
    PluginProjectValidation,
)
from app.plugins.plugin_validator import PluginValidation
from app.plugins.plugin_workbench import (
    FindingSeverity,
    PluginWorkbenchFinding,
)
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
    confirmations = []
    confirm_answers = []

    def factory():
        factory_calls.append(True)
        return PluginProjectGenerator()

    def start(target, callback):
        worker = BackgroundWorker(target, callback=callback)
        workers.append(worker)
        worker.start()
        return worker

    def confirm(title, text):
        confirmations.append((title, text))
        return confirm_answers.pop(0) if confirm_answers else False

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
            confirm=confirm,
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
        controller.draft.author = "DoctorSUS"
        controller.draft.project_name = "DoctorSUS Wizard Live Test"
        controller.set_plugin_id("")
        window.render()
        assert window._suggest_plugin_id()
        assert controller.draft.plugin_id == "doctorsus.wizard-live-test"
        controller.draft.project_name = "DoctorSUS wiz"
        controller.set_plugin_id("doctorsus.intentional")
        window.render()
        assert not window._suggest_plugin_id()
        assert controller.draft.plugin_id == "doctorsus.intentional"
        _, confirmation_text = confirmations[-1]
        assert "doctorsus.intentional" in confirmation_text
        assert "doctorsus.wiz" in confirmation_text
        confirm_answers.append(True)
        assert window._suggest_plugin_id()
        assert controller.draft.plugin_id == "doctorsus.wiz"
        controller.set_folder_name("")
        assert controller.apply_folder_suggestion() == "doctorsus-wiz"
        window.render()
        window.page_widgets["plugin_id"].event_generate("<FocusOut>")
        window.page_widgets["folder_name"].event_generate("<FocusOut>")
        assert pump(root, queue)
        assert not controller.draft.plugin_id_locked
        assert not controller.draft.folder_name_locked
        controller.set_plugin_id("doctorsus.wizard-live-test")
        assert (
            controller.draft.folder_name
            == "doctorsus-wizard-live-test"
        )
        controller.set_folder_name("custom folder")
        window.render()
        assert not window._suggest_folder()
        assert controller.draft.folder_name == "custom folder"
        confirm_answers.append(True)
        assert window._suggest_folder()
        assert (
            controller.draft.folder_name
            == "doctorsus-wizard-live-test"
        )
        controller.set_folder_name("custom reviewed folder")
        window.render()
        controller.set_plugin_id("susadb.skeleton-module")
        try:
            window._validate_step()
        except ValueError as exc:
            assert "reserved" in str(exc).casefold()
        else:
            raise AssertionError("Reserved identity was not rejected.")
        controller.set_plugin_id("example-author.wizard-gui-fixture")
        controller.set_folder_name("custom reviewed folder")

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
        review_text = window.review_summary_widget.get("1.0", "end")
        assert "Project folder: custom reviewed folder" in review_text
        assert (
            "Starter ZIP: "
            "example-author.wizard-gui-fixture-0.1.0.zip"
            in review_text
        )
        assert "Custom folder name retained by operator." in review_text
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
        advisory_text = "\n".join(
            detail.cget("text") for _card, detail in window.advisory_widgets
        )
        assert advisory_text.count("tests/test_lifecycle.py") == 1
        assert "VAL002: Production validation warning" not in advisory_text
        assert ";" not in advisory_text
        review_measurements = (
            bounds(window.viewport),
            bounds(window.review_summary_widget),
            bounds(window.validation_label),
            tuple(bounds(card) for card, _detail in window.advisory_widgets),
            window.status.winfo_rooty() + window.status.winfo_height(),
            window.winfo_rooty() + window.winfo_height(),
            window.viewport.scrollbar.winfo_width(),
        )

        modes[0] = "advanced"
        window.apply_mode()
        assert controller.validated
        advanced_titles = "\n".join(
            card.winfo_children()[0].cget("text")
            for card, _detail in window.advisory_widgets
        )
        assert "VAL002" in advanced_titles
        assert advanced_titles.count("VAL002") == 1
        real_validation = controller.validation
        unexpected_warning = (
            "Undeclared executable/native files: "
            "tests/test_lifecycle.py, extra.py, native.so"
        )
        controller.validation = PluginProjectValidation(
            True,
            production=PluginValidation(warnings=(unexpected_warning,)),
            workbench=SimpleNamespace(findings=(
                PluginWorkbenchFinding(
                    "VAL002", FindingSeverity.WARNING, "Package",
                    "Production validation warning", unexpected_warning,
                    "Review before packaging.",
                ),
            )),
        )
        window._render_validation_projection()
        unexpected_text = "\n".join(
            detail.cget("text") for _card, detail in window.advisory_widgets
        )
        assert unexpected_text.count("tests/test_lifecycle.py") == 1
        assert "extra.py" in unexpected_text and "native.so" in unexpected_text
        controller.validation = real_validation
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
        router = window.viewport.router
        assert router.count > 0
        window.close()
        assert router.count == 0
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
            f"review={review_measurements} "
            "steps=7 wheel-touchpad-native-dialog-guard=PASS "
            "identity-folder-ownership-warning-normalization=PASS "
            "reserved-id-high-impact-explicit-validation=PASS "
            "folder-zip-brief-workbench-static-handoff=PASS "
            "guided-advanced-draft-cleanup=PASS"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
