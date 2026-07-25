import unittest
from app.core.runtime_explorer_models import *

class RuntimeExplorerModelTests(unittest.TestCase):
 def test_java_records_and_serialization(self):
  c=JavaClassRecord("com.example.LongName",device_serial="D",target_identifier="T");self.assertEqual(c.namespace,"com.example");self.assertIn("LongName",c.display_label)
  m=JavaMethodRecord(c.class_name,"run",2,("java.lang.String","int"),"boolean");self.assertEqual(m.signature,"com.example.LongName.run(java.lang.String, int): boolean");self.assertEqual(m.to_dict()["overload_index"],2)
  f=JavaFieldRecord(c.class_name,"value","java.lang.String",value_preview="x");self.assertIn("value",f.display_label)
 def test_native_hook_and_event(self):
  module=NativeModuleRecord("libx.so","/data/libx.so","0x1",10);symbol=NativeSymbolRecord("open","function","0x2",module.module_name);self.assertIn("/data",module.display_label);self.assertIn("open",symbol.display_label)
  hook=RuntimeHookSpec(HookTarget.JAVA_METHOD,"C","m",("int",),modification_settings={"mode":"replace-return","value":1},changes_runtime=True,selected_target="pkg");self.assertEqual(hook.classification,"state-changing");self.assertEqual(hook.required_scope_category,"state-changing-testing")
  event=RuntimeEvent(RuntimeEventType.METHOD_ENTER,hook.hook_id,"C","m",arguments=(1,),payload={"x":1});self.assertEqual(event.to_dict()["event_type"],"method-enter");self.assertIn("C!m",event.display_text)
