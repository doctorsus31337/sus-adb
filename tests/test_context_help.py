import unittest

from app.core.context_help import HelpRegistry


class ContextHelpTests(unittest.TestCase):
    REQUIRED_TOPICS = {
        "console", "instrumentation-overview", "targets", "sessions",
        "script-studio", "pentest-dashboard", "adb-explorer",
        "runtime-explorer", "network", "storage", "apk-laboratory",
        "findings-reports", "plugin-manager", "addons-center",
        "device-rescue", "readiness-advisor", "webview-inspector",
        "sessions-center", "learning-center",
    }
    REQUIRED_TERMS = {
        "ADB", "package", "process", "PID", "attach", "spawn",
        "Frida Server", "Frida Gadget", "root", "bootloader",
        "port forwarding", "RPC", "Script Studio", "runtime target",
        "APK", "ABI", "arm64", "x86_64", "scope", "evidence",
        "finding", "user app", "system app", "debuggable app",
    }

    def test_required_topics_are_complete_and_local(self):
        registry = HelpRegistry()
        topics = {topic.topic_id: topic for topic in registry.topics()}
        self.assertTrue(self.REQUIRED_TOPICS <= topics.keys())
        for topic in topics.values():
            self.assertTrue(topic.purpose)
            self.assertTrue(topic.prerequisites)
            self.assertTrue(topic.quick_start)
            self.assertTrue(topic.controls)
            self.assertTrue(topic.terminology)
            self.assertTrue(topic.empty_states)
            self.assertTrue(topic.common_errors)
            self.assertTrue(topic.safe_example)
            self.assertTrue(topic.related_tools)
            self.assertIn("Guided", topic.mode_notes)
            self.assertNotIn("http", topic.searchable_text)

    def test_glossary_contains_and_searches_required_terms(self):
        registry = HelpRegistry()
        terms = {entry.term for entry in registry.glossary()}
        self.assertTrue(self.REQUIRED_TERMS <= terms)
        results = registry.search_glossary("temporary numeric")
        self.assertEqual([entry.term for entry in results], ["PID"])
        self.assertEqual(
            registry.search_topics("one-shot")[0].topic_id, "console"
        )


if __name__ == "__main__":
    unittest.main()
