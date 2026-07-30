import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class LogcatInvestigatorGUIContractTests(unittest.TestCase):
    def setUp(self):
        self.panel = (ROOT / "app/gui/logcat_investigator_panel.py").read_text(
            encoding="utf-8"
        )
        self.main = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")

    def test_host_workspace_is_narrow_capability_gated_and_lazy(self):
        self.assertIn('"logcat-investigator":HostWorkspaceBinding(', self.main)
        self.assertIn('"read-device-logs",True,("read-selected-device",)', self.main)
        self.assertIn("def _build_logcat_investigator_workspace", self.main)
        self.assertNotIn("LogcatCaptureService(", self.main.split(
            "def _initialize_core_services", 1
        )[1].split("def _build_logcat_investigator_workspace", 1)[0])

    def test_panel_has_required_controls_filters_and_read_only_transcript(self):
        for text in (
            "Start Capture",
            "Pause View",
            "Resume View",
            "Stop",
            "Clear View",
            "Reset Filters",
            "Tag contains",
            "Exact PID",
            "Message contains",
            "Dropped:",
            "View paused; capture continues in memory.",
        ):
            self.assertIn(text, self.panel)
        self.assertIn("ReadOnlyTextView(", self.panel)
        self.assertIn('font=theme["terminal_font"]', self.panel)
        self.assertNotIn("logcat -c", self.panel)
        self.assertNotIn("import subprocess", self.panel)

    def test_panel_uses_host_dispatch_worker_and_complete_cleanup(self):
        self.assertIn("self.start_background(operation", self.panel)
        self.assertIn("self.ui_dispatch(finished, result)", self.panel)
        self.assertIn("self.subscription.cancel()", self.panel)
        self.assertIn("self.capture_service.close", self.panel)
        self.assertIn("self.transcript.close()", self.panel)


if __name__ == "__main__":
    unittest.main()
