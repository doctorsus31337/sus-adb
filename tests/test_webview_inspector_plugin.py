import json,unittest
from pathlib import Path
from official_plugin_helpers import load
M=load("official_webview","webview_security_inspector");ROOT=Path(__file__).parents[1]
class T(unittest.TestCase):
 def test_static_candidates_bridges_settings_and_exports(self):
  text='WebView w; w.getSettings().setJavaScriptEnabled(true); w.addJavascriptInterface(obj,"Bridge"); w.getSettings().setAllowUniversalAccessFromFileURLs(true); handler.proceed(); android:usesCleartextTraffic="true"';items=M.scan_text(text,"Synthetic.java");rules={v.rule for v in items};self.assertTrue({"webview-usage","javascript-enabled","javascript-bridge","universal-file-url-access","ssl-continue-candidate","cleartext"}<=rules);self.assertTrue(all(v.confidence=="candidate" for v in items));self.assertEqual(json.loads(M.export_json(items))["candidates"][0]["confidence"],"candidate");self.assertIn("not confirmed",M.export_markdown(items))
 def test_structured_runtime_event_and_observation_only_agent(self):
  event=M.runtime_event({"payload":{"type":"navigation","class":"WebView","url":"x"*500}});self.assertEqual(len(event.url),240);agent=(ROOT/"plugins/official/webview_security_inspector/assets/webview_observer.js").read_text();self.assertIn("Java.available",agent);self.assertNotIn("handler.proceed",agent);self.assertNotIn("evaluateJavascript",agent);self.assertNotIn("return false",agent.casefold());meta=json.loads((ROOT/"plugins/official/webview_security_inspector/assets/webview_observer.meta.json").read_text());self.assertFalse(meta["auto_load"]);self.assertEqual(meta["trust"],"untrusted")
 def test_templates_and_no_real_frida_import(self):self.assertGreaterEqual(len(M.FINDING_TEMPLATES),9);self.assertNotIn("import frida",Path(M.__file__).read_text())
