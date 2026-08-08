import unittest
from types import SimpleNamespace

from app.core.command_result import CommandResult
from app.core.frida_manager import FridaDiagnosis
from app.gui.instrumentation_panel import InstrumentationPanel
from app.gui.main_window import SusADBWindow


class Widget:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def cget(self, name):
        return self.options.get(name)


class Workspace:
    def __init__(self):
        self.current = "Sessions"

    def set(self, name):
        self.current = name


class Objection:
    def __init__(self, readiness):
        self.next_readiness = readiness
        self.readiness_calls = []
        self.launch_calls = []

    def readiness(self, serial, target, transport, **options):
        self.readiness_calls.append((serial, target, transport, options))
        return self.next_readiness

    def launch_external_session(self, command):
        self.launch_calls.append(tuple(command))


class PanelHarness:
    validate_objection = InstrumentationPanel.validate_objection
    _show_objection_readiness = InstrumentationPanel._show_objection_readiness
    _reveal_validation_results = InstrumentationPanel._reveal_validation_results
    _report_failure = InstrumentationPanel._report_failure

    def __init__(self, plan, readiness=None):
        self.plan = plan
        self.internal_workspace = Workspace()
        self.session_notice = Widget()
        self.overview_notice = Widget()
        self.summary_labels = {"warning": Widget()}
        self.theme = {"error": "error", "success": "success"}
        self.appended = []
        self.logged = []
        self.operation_titles = []
        self.objection = Objection(
            readiness or SimpleNamespace(ready=True, errors=())
        )

    def _build_objection_plan(self, _spawn):
        return self.plan

    def _append_results(self, title, text):
        self.appended.append((title, text))

    def _run_operation(self, title, target, callback):
        self.operation_titles.append(title)
        callback(target())

    def log(self, message):
        self.logged.append(message)


class StatusBarHarness:
    def __init__(self):
        self.frida = "Stopped"

    def set_status(self, **values):
        if "frida" in values:
            self.frida = values["frida"]


class WindowStatusHarness:
    apply_status = SusADBWindow._apply_instrumentation_frida_status

    def __init__(self):
        self.devices = SimpleNamespace(
            selected=SimpleNamespace(serial="SERIAL", frida=False)
        )
        self.status_bar = StatusBarHarness()
        self.published = []

    def _publish_host_state(self, lifecycle):
        self.published.append(lifecycle)


class FridaStatusHarness:
    FRIDA_HEADER_STATES = InstrumentationPanel.FRIDA_HEADER_STATES
    _frida_status_from_diagnosis = staticmethod(
        InstrumentationPanel._frida_status_from_diagnosis
    )
    _set_frida_status = InstrumentationPanel._set_frida_status
    _show_frida_diagnosis = InstrumentationPanel._show_frida_diagnosis
    _complete_lifecycle = InstrumentationPanel._complete_lifecycle
    _state = staticmethod(InstrumentationPanel._state)

    def __init__(self):
        self.window = WindowStatusHarness()
        self.device = SimpleNamespace(serial="SERIAL")
        self.frida_status_callback = lambda serial, status, running: (
            self.window.apply_status(serial, status, running)
        )
        self.frida_labels = {
            name: Widget()
            for name in ("path", "running", "version", "match", "27042", "27043", "reachable")
        }
        self.summary_labels = {
            name: Widget()
            for name in ("root", "server", "reachable", "versions", "warning")
        }
        self.overview_notice = Widget()
        self.theme = {"error": "error", "gold": "gold"}
        self.appended = []
        self.logged = []
        self.cleared = []
        self._last_diagnosis = None

    def _append_results(self, title, text):
        self.appended.append((title, text))

    def _update_mismatch_warning(self):
        return None

    def _complete_stale_operation(self, value, reason):
        self.cleared.append((value, reason))

    def log(self, message):
        self.logged.append(message)


def diagnosis(*, path="/data/local/tmp/frida-server", running=True,
              reachable=True, match=True):
    return FridaDiagnosis(
        "SERIAL", True, True, running, path, "17.2.1",
        "17.2.1" if path else None, match, reachable, reachable, reachable,
        recommendations=("Fixture diagnosis.",),
    )


def ready_plan():
    return SimpleNamespace(
        ready=True,
        errors=(),
        descriptor=SimpleNamespace(
            device_serial="SERIAL",
            target="org.example.fixture",
            transport="network",
            network_host="127.0.0.1",
            network_port=27042,
        ),
    )


class InstrumentationFeedbackTests(unittest.TestCase):
    def test_frida_diagnosis_states_update_header_global_status_and_device_snapshot(self):
        cases = (
            (diagnosis(), "Server running", "Running", True),
            (diagnosis(running=False), "Server stopped", "Stopped", False),
            (diagnosis(path=None, running=False, match=None), "Server missing", "Missing", False),
            (diagnosis(reachable=False), "Server unreachable", "Unreachable", True),
            (diagnosis(match=False), "Version mismatch", "Version mismatch", True),
        )
        for result, header, global_status, running in cases:
            with self.subTest(global_status=global_status):
                panel = FridaStatusHarness()
                panel._show_frida_diagnosis(result)
                self.assertEqual(panel.frida_labels["running"].cget("text"), header)
                self.assertEqual(panel.summary_labels["server"].cget("text"), header)
                self.assertEqual(panel.window.status_bar.frida, global_status)
                self.assertEqual(panel.window.devices.selected.frida, running)

    def test_start_and_stop_diagnose_transitions_cannot_leave_stale_status(self):
        panel = FridaStatusHarness()
        success = CommandResult.from_command(("fixture",), 0, stdout="ok")

        panel._set_frida_status("Starting", serial="SERIAL")
        panel._complete_lifecycle(success, "Start", "SERIAL")
        panel._show_frida_diagnosis(diagnosis())
        self.assertEqual(panel.summary_labels["server"].cget("text"), "Server running")
        self.assertEqual(panel.window.status_bar.frida, "Running")

        panel._set_frida_status("Stopping", serial="SERIAL")
        panel._complete_lifecycle(success, "Stop", "SERIAL")
        panel._show_frida_diagnosis(diagnosis(running=False))
        self.assertEqual(panel.summary_labels["server"].cget("text"), "Server stopped")
        self.assertEqual(panel.window.status_bar.frida, "Stopped")

    def test_failed_frida_command_is_consistent_and_does_not_guess_running_state(self):
        panel = FridaStatusHarness()
        panel.window.devices.selected.frida = True
        failure = CommandResult.from_command(
            ("fixture",), 1, stderr="command failed"
        )

        panel._complete_lifecycle(failure, "Restart", "SERIAL")

        self.assertEqual(panel.frida_labels["running"].cget("text"), "Command failed")
        self.assertEqual(panel.summary_labels["server"].cget("text"), "Command failed")
        self.assertEqual(panel.window.status_bar.frida, "Command failed")
        self.assertTrue(panel.window.devices.selected.frida)

    def test_status_completion_for_an_old_serial_is_ignored_globally(self):
        window = WindowStatusHarness()
        window.apply_status("OTHER", "Running", True)
        self.assertEqual(window.status_bar.frida, "Stopped")
        self.assertFalse(window.devices.selected.frida)
        self.assertFalse(window.published)

    def test_objection_attach_and_spawn_prerequisite_guidance_is_explicit(self):
        guidance = InstrumentationPanel.OBJECTION_SESSION_GUIDANCE
        self.assertIn("Attach requires the selected app/process to already be running.", guidance)
        self.assertIn("Open or otherwise start it on the device first.", guidance)
        self.assertIn("Spawn starts a non-running target.", guidance)

    def test_invalid_validation_plan_reveals_unchanged_error(self):
        panel = PanelHarness(
            SimpleNamespace(ready=False, errors=("No device is selected.",))
        )

        panel.validate_objection()

        self.assertEqual(panel.internal_workspace.current, "Results")
        self.assertEqual(panel.session_notice.options["text"], "No device is selected.")
        self.assertEqual(
            panel.appended,
            [("Objection validation", "No device is selected.")],
        )
        self.assertFalse(panel.objection.readiness_calls)
        self.assertFalse(panel.objection.launch_calls)

    def test_validation_success_reveals_results_without_launching(self):
        panel = PanelHarness(ready_plan())

        panel.validate_objection()

        self.assertEqual(panel.internal_workspace.current, "Results")
        self.assertEqual(
            panel.session_notice.options["text"],
            "Objection readiness checks passed.",
        )
        self.assertEqual(
            panel.appended,
            [("Objection validation", "Objection readiness checks passed.")],
        )
        self.assertEqual(
            panel.objection.readiness_calls,
            [
                (
                    "SERIAL", "org.example.fixture", "network",
                    {"host": "127.0.0.1", "port": 27042},
                )
            ],
        )
        self.assertFalse(panel.objection.launch_calls)

    def test_validation_failure_reveals_exact_readiness_errors(self):
        errors = (
            "Objection was not found.",
            "Frida is not reachable on the selected device.",
        )
        panel = PanelHarness(
            ready_plan(), SimpleNamespace(ready=False, errors=errors)
        )

        panel.validate_objection()

        expected = "\n".join(errors)
        self.assertEqual(panel.internal_workspace.current, "Results")
        self.assertEqual(panel.session_notice.options["text"], expected)
        self.assertEqual(panel.appended, [("Objection validation", expected)])
        self.assertFalse(panel.objection.launch_calls)

    def test_validation_exception_failure_also_reveals_results(self):
        panel = PanelHarness(ready_plan())

        panel._report_failure("Objection validation", "readiness failed")

        self.assertEqual(panel.internal_workspace.current, "Results")
        self.assertEqual(
            panel.appended,
            [("Objection validation failed", "readiness failed")],
        )
        self.assertEqual(panel.session_notice.options["text"], "readiness failed")


if __name__ == "__main__":
    unittest.main()
