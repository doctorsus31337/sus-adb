import json
import tempfile
import unittest
from pathlib import Path

from app.core.learning_center import (
    LearningCenterService,
    LearningProgressStore,
)
from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore
from official_plugin_helpers import load


ROOT = Path(__file__).parents[1]
FRIDA = load("official_frida_tutorial", "frida_tutorial")
OBJECTION = load("official_objection_tutorial", "objection_tutorial")


class LearningCenterTests(unittest.TestCase):
    def manager(self, directory):
        store = PluginStore(Path(directory) / "plugins")
        registry = ContributionRegistry()
        manager = PluginManager(
            store,
            PluginTrustStore(store.root / "state/trust.json"),
            registry,
            official_root=ROOT / "plugins/official",
        )
        progress = LearningProgressStore(
            Path(directory) / "learning-progress.json"
        )
        return manager, registry, LearningCenterService(
            manager, registry, progress
        )

    def test_course_content_counts_and_required_device_gone_explanation(self):
        frida = FRIDA.course_spec()
        objection = OBJECTION.course_spec()
        self.assertEqual(len(frida.lessons), 15)
        self.assertEqual(len(objection.lessons), 14)
        self.assertTrue(frida.synthetic_only and objection.synthetic_only)
        self.assertFalse(frida.device_actions or objection.device_actions)
        contextual = next(
            lesson for lesson in objection.lessons
            if lesson.lesson_id == "contextual-help"
        )
        self.assertIn("help/reference command", contextual.explanation)
        self.assertIn("not the action itself", contextual.explanation)
        device_gone = next(
            lesson for lesson in objection.lessons
            if lesson.lesson_id == "device-gone"
        )
        self.assertIn("help command may succeed", device_gone.explanation)
        self.assertIn("device is gone", device_gone.synthetic_example)

    def test_assistant_manifests_are_disabled_minimum_capability_and_safe(self):
        for directory in ("frida_tutorial", "objection_tutorial"):
            root = ROOT / "plugins/official" / directory
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertFalse(manifest["enabled"])
            self.assertEqual(
                manifest["requested_capabilities"],
                ["read-selected-device", "read-selected-target"],
            )
            self.assertEqual(
                manifest["contributed_components"][0]["contribution_type"],
                "pentest-panel",
            )
            self.assertEqual(
                manifest["contributed_components"][-1]["contribution_type"],
                "learning-course",
            )
            source = (root / "plugin.py").read_text()
            for forbidden in (
                "subprocess", "requests", "socket", "execution_callback",
                "load_frida_script", "run_adb",
            ):
                self.assertNotIn(forbidden, source)

    def test_progress_bookmarks_and_exercises_are_local_and_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LearningProgressStore(
                Path(directory) / "learning-progress.json"
            )
            manager, registry, service = self.manager(directory)
            course = FRIDA.course_spec()
            lesson = course.lessons[0]
            service.progress_store = store
            self.assertTrue(service.mark_complete(course, lesson))
            self.assertTrue(service.bookmark(course, lesson))
            self.assertTrue(service.record_exercise(course, lesson))
            loaded = store.load()[course.course_id]
            self.assertEqual(loaded.completed, (lesson.lesson_id,))
            self.assertEqual(loaded.bookmarks, (lesson.lesson_id,))
            self.assertEqual(loaded.exercises, (lesson.lesson_id,))
            raw = (Path(directory) / "learning-progress.json").read_text()
            self.assertNotIn("serial", raw.casefold())
            self.assertNotIn("target", raw.casefold())

    def test_lifecycle_is_explicit_before_course_becomes_browsable(self):
        with tempfile.TemporaryDirectory() as directory:
            manager, registry, service = self.manager(directory)
            addons = service.educational_addons()
            self.assertEqual(len(addons), 2)
            self.assertTrue(all(not item.installed for item in addons))
            self.assertFalse(service.courses())
            item = next(
                value for value in manager.official()
                if value.manifest.plugin_id == "susadb.frida-tutorial"
            )
            self.assertTrue(
                manager.install_official(
                    item.manifest.plugin_id, item.package_digest
                ).ok
            )
            self.assertFalse(service.courses())
            self.assertTrue(manager.approve(
                item.manifest.plugin_id,
                item.manifest.requested_capabilities,
            ).ok)
            self.assertTrue(manager.enable(item.manifest.plugin_id).ok)
            self.assertFalse(service.courses())
            self.assertTrue(manager.load(item.manifest.plugin_id).ok)
            self.assertEqual(
                service.courses()[0].course_id, "frida-foundations"
            )
            self.assertEqual(
                registry.list("learning-course")[0].plugin_id,
                "susadb.frida-tutorial",
            )


if __name__ == "__main__":
    unittest.main()
