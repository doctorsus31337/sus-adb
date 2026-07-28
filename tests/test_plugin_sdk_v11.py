import json,tempfile,unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType,SimpleNamespace

from app.plugins.plugin_interactive import *
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_ui import PluginPanelSpec,PluginView
from app.plugins.plugin_validator import PluginValidator


class PluginSDKV11Tests(unittest.TestCase):
    def package(self,root,api):
        root=Path(root);(root/"manifest.json").write_text(json.dumps({"plugin_id":"sdk.fixture","name":"SDK","version":"1.0.0","entry_point":"plugin.py:Plugin","plugin_api_version":api}),encoding="utf-8");(root/"plugin.py").write_text("raise RuntimeError('static only')\n",encoding="utf-8")
        return PluginPackage.inspect(root)
    def test_api_10_and_11_are_supported_future_is_rejected(self):
        for api in ("1.0","1.1"):
            with tempfile.TemporaryDirectory() as root:self.assertTrue(PluginValidator().validate(self.package(root,api)).valid)
        with tempfile.TemporaryDirectory() as root:self.assertFalse(PluginValidator().validate(self.package(root,"2.0")).valid)
    def test_specs_are_immutable_and_v10_panel_has_no_actions(self):
        field=PluginFieldSpec("name","Name")
        with self.assertRaises(FrozenInstanceError):field.label="Changed"
        panel=PluginPanelSpec("Legacy",(PluginView("Overview","unchanged"),))
        self.assertEqual(panel.actions,())
    def test_duplicate_field_and_action_ids_are_rejected(self):
        field=PluginFieldSpec("same","Same")
        self.assertRaises(ValueError,PluginFormSpec,"form",(field,field))
        action=PluginActionSpec("same","Same",lambda _request:PluginActionResult(True))
        self.assertRaises(ValueError,PluginPanelSpec,"Panel",(),{},(action,action))
    def test_field_types_and_bounds_validate(self):
        self.assertRaises(ValueError,PluginFieldSpec,"x","X","future")
        required=PluginFieldSpec("name","Name",required=True,max_length=3)
        self.assertRaises(ValueError,validate_field_value,required,"")
        self.assertRaises(ValueError,validate_field_value,required,"long")
        integer=PluginFieldSpec("count","Count",PluginFieldType.INTEGER,minimum=1,maximum=3)
        self.assertEqual(validate_field_value(integer,"2"),2)
        self.assertRaises(ValueError,validate_field_value,integer,4)
        choice=PluginFieldSpec("choice","Choice",PluginFieldType.CHOICE,options=(PluginOptionSpec("one","One"),))
        self.assertRaises(ValueError,validate_field_value,choice,"two")
    def test_sensitive_and_password_contracts_remain_runtime_only(self):
        secret=PluginFieldSpec("secret","Secret",PluginFieldType.PASSWORD,sensitive=True)
        form=PluginFormSpec("credentials",(secret,))
        values=validate_form(form,{"secret":"private-value"})
        self.assertIsInstance(values,MappingProxyType)
        self.assertNotIn("private-value",repr(secret))
    def test_state_change_requires_confirmation(self):
        self.assertRaises(ValueError,PluginActionSpec,"change","Change",lambda _request:PluginActionResult(True),classification=PluginActionClassification.STATE_CHANGING)
    def test_request_is_sanitized_immutable_and_result_uses_ok(self):
        context=SimpleNamespace(selected_device=MappingProxyType({}),selected_target=MappingProxyType({}))
        request=PluginActionRequest("inspect",{"value":"safe"},context)
        with self.assertRaises(TypeError):request.values["value"]="changed"
        result=PluginActionResult(True,"done")
        self.assertTrue(result.ok);self.assertFalse(hasattr(result,"success"))
    def test_progress_and_navigation_are_bounded(self):
        self.assertRaises(ValueError,PluginProgressUpdate,"bad",2)
        self.assertEqual(PluginNavigationSpec("workspace-home").destination,"workspace-home")
        self.assertRaises(ValueError,PluginNavigationSpec,"run-command")
    def test_panel_construction_never_invokes_action(self):
        calls=[]
        action=PluginActionSpec("explicit","Explicit",lambda request:calls.append(request) or PluginActionResult(True))
        PluginPanelSpec("Panel",(),actions=(action,))
        self.assertEqual(calls,[])


if __name__=="__main__":unittest.main()
