import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class LogcatInvestigatorAnalysisGUIContractTests(unittest.TestCase):
    def setUp(self):
        self.panel = (
            ROOT / "app/gui/logcat_investigator_panel.py"
        ).read_text(encoding="utf-8")
        self.smoke = (
            ROOT / "scripts/run_logcat_investigator_analysis_smoke.py"
        )

    def test_events_keep_transcript_and_use_existing_analysis_owner(self):
        self.assertIn("self.capture_service = capture_service", self.panel)
        self.assertIn(
            "self.analysis_service = capture_service.analysis_service", self.panel
        )
        self.assertIn("self.transcript_page", self.panel)
        self.assertIn("self.events_page = None", self.panel)
        self.assertNotIn("LogcatCaptureService(", self.panel)
        self.assertNotIn("BackgroundWorker(", self.panel)

    def test_filters_details_navigation_pause_clear_and_privacy_contract(self):
        for text in (
            "Event filters:",
            "Process/package contains",
            "Search events",
            "Unique:",
            "Visible:",
            "Occurrences:",
            "Dropped groups:",
            "Detector/rule:",
            "Reconstructed Stack",
            "Bounded Raw Context",
            "without changing transcript ",
            "capture and analysis continue in memory",
            "self.analysis_service.reset_filters()",
            "self.capture_service.clear()",
        ):
            self.assertIn(text, self.panel)
        self.assertNotIn("logcat -c", self.panel)
        self.assertNotIn("regex", self.panel.casefold())

    def test_dedicated_acceptance_runner_is_fake_only_and_complete(self):
        source = self.smoke.read_text(encoding="utf-8")
        self.assertIn("FakeProcessFactory", source)
        self.assertIn("records=0,1,100,1000,10000", source)
        self.assertIn("events=0,1,100,1000,duplicate-heavy-overflow", source)
        self.assertIn("900, 650", source)
        self.assertIn("980, 700", source)
        self.assertIn("1180, 780", source)
        self.assertIn("1400, 860", source)
        self.assertIn("1.0, 1.25, 1.5", source)
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("socket", source)


if __name__ == "__main__":
    unittest.main()
