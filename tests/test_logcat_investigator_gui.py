import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class LogcatInvestigatorGUIContractTests(unittest.TestCase):
    def setUp(self):
        self.panel = (ROOT / "app/gui/logcat_investigator_panel.py").read_text(
            encoding="utf-8"
        )
        self.main = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")
        self.timeline = (
            ROOT / "app/gui/logcat_event_timeline.py"
        ).read_text(encoding="utf-8")

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
            "View paused; capture and analysis continue in memory.",
            "Transcript",
            "Events",
            "Reset Analysis Filters",
            "Show in Transcript",
            "Return to Live View",
            "Context is no longer present in the bounded Logcat buffer.",
        ):
            self.assertIn(text, self.panel)
        self.assertIn("ReadOnlyTextView(", self.panel)
        self.assertIn('font=theme["terminal_font"]', self.panel)
        self.assertNotIn("logcat -c", self.panel)
        self.assertNotIn("import subprocess", self.panel)

    def test_event_view_is_lazy_virtualized_responsive_and_read_only(self):
        self.assertIn("if self.events_page is not None:", self.panel)
        self.assertIn("from app.gui.logcat_event_timeline import", self.panel)
        self.assertIn("self.winfo_width() >= 1_100", self.panel)
        self.assertIn("self._compact_event_details", self.panel)
        for name in ("event_details", "event_stack", "event_context"):
            self.assertIn(f"self.{name} = ReadOnlyTextView(", self.panel)
        self.assertIn("class LogcatEventTimeline(", self.timeline)
        self.assertIn("self.events = tuple(events)[:1_000]", self.timeline)
        self.assertIn("def _visible_range(", self.timeline)
        self.assertIn("View Details", self.timeline)
        self.assertIn("Show in Transcript", self.timeline)
        self.assertNotIn("CTkScrollableFrame", self.timeline)
        self.assertNotIn("import subprocess", self.timeline)

    def test_panel_uses_host_dispatch_worker_and_complete_cleanup(self):
        self.assertIn("self.start_background(operation", self.panel)
        self.assertIn("self.ui_dispatch(finished, result)", self.panel)
        self.assertIn("self.subscription.cancel()", self.panel)
        self.assertIn("self.capture_service.close", self.panel)
        self.assertIn("self.transcript.close()", self.panel)
        self.assertIn("self.event_timeline.close()", self.panel)
        self.assertIn("self.bindings.close()", self.panel)


if __name__ == "__main__":
    unittest.main()
