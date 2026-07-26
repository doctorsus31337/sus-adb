import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from app.plugins.plugin_workbench import PluginWorkbenchAnalyzer


BASE="""\
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_interactive import PluginActionResult, PluginActionSpec, PluginConfirmationSpec, PluginFieldSpec, PluginFormSpec, PluginNavigationSpec
from app.plugins.plugin_ui import PluginPanelSpec
def callback(request): return PluginActionResult(True, "done")
def panel_spec(_context=None):
    field = PluginFieldSpec("name", "Name")
    form = PluginFormSpec("form", (field,))
    action = PluginActionSpec("inspect", "Inspect", callback, form=form)
    return PluginPanelSpec("Panel", (), actions=(action,))
class Plugin:
    def activate(self, api): return (Contribution("fixture.panel", "pentest-panel", "Fixture", factory=panel_spec),)
    def deactivate(self): pass
"""


class PluginSDKV11WorkbenchTests(unittest.TestCase):
    def analyze(self,source,api="1.1"):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest={"plugin_id":"fixture.v11","name":"Fixture","version":"1.0.0","entry_point":"plugin.py:Plugin","plugin_api_version":api,"requested_capabilities":[],"contributed_components":[{"contribution_id":"fixture.panel","contribution_type":"pentest-panel","title":"Fixture","factory":"panel_spec"}]}
            (root/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8");(root/"plugin.py").write_text(source,encoding="utf-8")
            with patch("builtins.__import__",wraps=__import__) as importer:snapshot=PluginWorkbenchAnalyzer().analyze(root)
            self.assertFalse(any(call.args and str(call.args[0]).startswith("sus_adb_plugin_") for call in importer.call_args_list))
            return snapshot
    def rules(self,snapshot):return {value.rule_id for value in snapshot.findings}
    def test_valid_contract_is_recognized_without_execution(self):
        snapshot=self.analyze(BASE);self.assertIn("SDK100",self.rules(snapshot));self.assertNotIn("SDK110",self.rules(snapshot))
    def test_v11_symbols_under_v10_are_blocked(self):
        self.assertIn("SDK110",self.rules(self.analyze(BASE,"1.0")))
    def test_duplicate_actions_state_confirmation_navigation_and_sensitive_default(self):
        source=BASE.replace(
            'action = PluginActionSpec("inspect", "Inspect", callback, form=form)',
            'action = PluginActionSpec("same", "One", callback, form=form)\n'
            '    duplicate = PluginActionSpec("same", "Two", callback)\n'
            '    change = PluginActionSpec("change", "Change", callback, classification="state_changing")\n'
            '    nav = PluginNavigationSpec("run-command")\n'
            '    secret = PluginFieldSpec("secret", "Secret", default="literal", sensitive=True)'
        )
        rules=self.rules(self.analyze(source))
        self.assertTrue({"SDK111","SDK112","SDK113","SDK116"}<=rules)


if __name__=="__main__":unittest.main()
