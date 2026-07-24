import unittest

from app.core.script_operation import (
    OperationState,
    ScriptBadge,
    ScriptOperationModel,
)
from app.core.script_validator import ScriptValidation


class ScriptOperationTests(unittest.TestCase):
    def model(self):
        return ScriptOperationModel(clock=lambda: "2026-07-24T12:00:00+00:00")

    def test_inline_operation_success_and_duplicate_click_prevention(self):
        model = self.model()
        self.assertTrue(
            model.begin(
                "Load script",
                script="agent.js",
                target="org.example.app",
                device="SERIAL",
                stage="Compiling",
            )
        )
        self.assertFalse(model.begin("Load script"))
        self.assertTrue(model.busy)
        model.succeed("Script loaded successfully.", ScriptBadge.LOADED)
        self.assertEqual(model.current.state, OperationState.SUCCESS)
        self.assertEqual(model.current.stage, "Complete")
        self.assertEqual(model.badge, ScriptBadge.LOADED)

    def test_compile_error_parses_source_line_and_retains_details(self):
        model = self.model()
        model.begin("Load script", stage="Compiling")
        model.fail(
            "JavaScript compilation failed",
            technical_details="Line 47: unexpected token `}`\ntrace",
        )
        self.assertEqual(model.current.error_line, 47)
        self.assertEqual(model.badge, ScriptBadge.ERROR)
        self.assertIn("trace", model.current.technical_details)
        for text, expected in (
            ("agent.js:19:4 syntax error", 19),
            ("lineNumber=8", 8),
        ):
            self.assertEqual(model.parse_source_line(text), expected)

    def test_edit_after_load_save_and_reload_required_state(self):
        model = self.model()
        model.loaded()
        model.edited(loaded=True)
        self.assertEqual(model.badge, ScriptBadge.RELOAD_REQUIRED)
        model.saved(loaded=True)
        self.assertEqual(model.badge, ScriptBadge.RELOAD_REQUIRED)
        model.loaded()
        self.assertEqual(model.badge, ScriptBadge.LOADED)
        model.edited(loaded=False)
        self.assertEqual(model.badge, ScriptBadge.UNSAVED)
        model.saved(loaded=False)
        self.assertEqual(model.badge, ScriptBadge.SAVED)
        model.unloaded()
        self.assertEqual(model.badge, ScriptBadge.UNLOADED)

    def test_load_versus_reload_guidance_is_explicit(self):
        self.assertIn(
            "Use Reload",
            ScriptOperationModel.load_guidance(True, edited=True),
        )
        self.assertIn(
            "already loaded",
            ScriptOperationModel.load_guidance(True),
        )
        self.assertIn(
            "active runtime session",
            ScriptOperationModel.load_guidance(False),
        )

    def test_advisories_default_hidden_and_suggestions_remain_on_demand(self):
        validation = ScriptValidation(
            True,
            warnings=("Digest changed.",),
            suggestions=("Check Java.available.",),
            advisories=("Generic advisory.",),
        )
        hidden = ScriptOperationModel.present_validation(
            validation, show_advisories=False
        )
        self.assertEqual(hidden.advisories, ())
        self.assertEqual(hidden.suggestions, ("Check Java.available.",))
        shown = ScriptOperationModel.present_validation(
            validation, show_advisories=True
        )
        self.assertEqual(shown.advisories, ("Generic advisory.",))


if __name__ == "__main__":
    unittest.main()
