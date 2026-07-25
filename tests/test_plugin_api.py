import tempfile,unittest
from app.core.host_state import DeviceState,HostStateSnapshot,HostStateStore
from app.plugins.plugin_api import PluginAPI
class T(unittest.TestCase):
 def test_gated_facades_and_sanitized_state(self):
  with tempfile.TemporaryDirectory() as d:
   a=PluginAPI("p",state_root=d);self.assertFalse(a.run_adb_readonly(("getprop",)).ok);b=PluginAPI("p",("run-adb-readonly","write-plugin-state","read-local-plugin-files"),state_root=d,adb_readonly=lambda x:x);self.assertTrue(b.run_adb_readonly(("getprop",)).ok);self.assertFalse(b.run_adb_readonly(("rm",)).ok);self.assertTrue(b.write_state({"x":1}).ok);self.assertEqual(b.read_state().value,{"x":1})
 def test_live_context_contains_only_sanitized_host_state(self):
  store=HostStateStore();store.publish(HostStateSnapshot(DeviceState("SERIAL","Pixel","Google","device","Google Pixel"),(DeviceState("SERIAL","Pixel","Google","device","Google Pixel"),),"device",interface_mode="guided"))
  hidden=PluginAPI("p",host_state=store).context();self.assertEqual(dict(hidden.selected_device),{});self.assertEqual(hidden.devices,())
  context=PluginAPI("p",("read-selected-device",),host_state=store).context();self.assertEqual(context.selected_device["serial"],"SERIAL");self.assertEqual(context.interface_mode,"guided");self.assertNotIn("manager",context.selected_device);self.assertNotIn("root",context.selected_device)
