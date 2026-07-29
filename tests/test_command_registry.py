import unittest

from app.core.command_registry import CommandRegistry
from app.core.command_router import CommandClassification, CommandRouter


class CommandRegistryTests(unittest.TestCase):
    def test_ids_and_syntax_are_unique_and_relationships_resolve(self):
        specs = CommandRegistry.specs()
        self.assertEqual(len({spec.command_id for spec in specs}), len(specs))
        self.assertEqual(len({spec.command for spec in specs}), len(specs))
        known = CommandRegistry.by_id()
        self.assertTrue(all(spec.command_id for spec in specs))
        self.assertTrue(
            all(
                relationship.command_id in known
                for spec in specs
                for relationship in spec.relationships
            )
        )

    def test_old_registry_callers_remain_compatible(self):
        grouped = CommandRegistry.grouped()
        commands = CommandRegistry.all_commands()
        rendered = CommandRegistry.render_text()
        self.assertIn("SUS COMPANION", grouped)
        self.assertIn("adb devices -l", commands)
        self.assertIn("adb devices -l", rendered)

    def test_guided_and_advanced_render_from_same_metadata(self):
        guided = CommandRegistry.render_text()
        advanced = CommandRegistry.render_text(advanced=True)
        for spec in CommandRegistry.specs():
            self.assertIn(spec.command, guided)
            self.assertIn(spec.command, advanced)
            self.assertIn(spec.description, guided)
        self.assertNotIn("Classification:", guided)
        self.assertIn("Classification: interactive", advanced)
        self.assertIn("Related: adb devices -l", advanced)

    def test_registry_classification_hints_match_router_for_concrete_commands(self):
        router = CommandRouter()
        expected = {
            "one-shot": CommandClassification.ONE_SHOT,
            "interactive": CommandClassification.INTERACTIVE,
            "streaming-but-finite": CommandClassification.STREAMING_FINITE,
        }
        for spec in CommandRegistry.specs():
            if spec.arguments or spec.command.startswith("cd "):
                continue
            with self.subTest(command=spec.command):
                self.assertEqual(
                    router.classify(spec.command).classification,
                    expected[spec.classification],
                )


if __name__ == "__main__":
    unittest.main()
