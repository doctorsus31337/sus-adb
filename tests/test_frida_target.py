import unittest
from dataclasses import FrozenInstanceError

from app.core.frida_target import FridaTarget, TargetType


class FridaTargetTests(unittest.TestCase):
    def test_model_is_immutable_and_builds_display_label(self):
        target = FridaTarget("Example", "com.example.app", 42, TargetType.APPLICATION, True)
        self.assertIn("com.example.app", target.display_label)
        self.assertIn("PID 42", target.display_label)
        with self.assertRaises(FrozenInstanceError):
            target.name = "Changed"

    def test_application_identifier_only_applies_to_applications(self):
        process = FridaTarget("System UI", None, 9, TargetType.PROCESS, True)
        self.assertIsNone(process.application_identifier)


if __name__ == "__main__":
    unittest.main()
