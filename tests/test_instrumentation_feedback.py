import unittest
from types import SimpleNamespace

from app.gui.instrumentation_panel import InstrumentationPanel


class Widget:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


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
