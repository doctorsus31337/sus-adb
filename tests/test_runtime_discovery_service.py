import unittest
from types import SimpleNamespace
from app.core.runtime_discovery_service import RuntimeDiscoveryService
from app.core.frida_target import FridaTarget,TargetType

class Result:
 def __init__(self,ok=True,value=None,error=None):self.ok=ok;self.value=value;self.error=error
class Script:
 def __init__(self,value):self.value=value;self.unloaded=False
class Adapter:
 def __init__(self):self.calls=0;self.scripts=[]
 def create_script(self,session,source):
  self.calls+=1
  if "readiness:function" in source:value={"javaAvailable":False}
  elif "java-class-discovery" in source:value={"items":[{"className":"com.app.A"},{"bad":1}]}
  elif "java-method-discovery" in source:value={"items":[{"methodName":"run","overloadIndex":1,"argumentTypes":["int"],"returnType":"void"}]}
  elif "java-field-discovery" in source:value={"items":[{"fieldName":"x","typeName":"int"},"bad"]}
  elif "native-module" in source:value={"items":[{"moduleName":"libx.so","path":"/x","baseAddress":"0x1","size":2}]}
  else:value={"items":[{"symbolName":"open","symbolType":"function","address":"0x2"}]}
  script=Script(value);self.scripts.append(script);return Result(value=script)
 def register_message_callback(self,s,c):return Result()
 def load_script(self,s):return Result()
 def call_export(self,s,n):return Result(value=s.value)
 def unload_script(self,s):s.unloaded=True;return Result()
class Runtime:
 def __init__(self):self.adapter=Adapter();self.session=object();self.serial="D";self.target=FridaTarget("App","com.app",1,TargetType.APPLICATION,True)
 def readiness(self,s,t):return Result()
class Cancel:
 def is_set(self):return True

class RuntimeDiscoveryTests(unittest.TestCase):
 def setUp(self):self.runtime=Runtime();self.service=RuntimeDiscoveryService(self.runtime,max_results=10);self.service.select("D",self.runtime.target)
 def test_missing_target_java_unavailable_and_cleanup(self):
  other=RuntimeDiscoveryService(self.runtime);self.assertFalse(other.enumerate_native_modules().ok)
  result=self.service.readiness();self.assertTrue(result.ok);self.assertFalse(self.service.java_available);self.assertTrue(self.runtime.adapter.scripts[-1].unloaded)
 def test_classes_methods_fields_cache_and_local_filter(self):
  self.assertTrue(self.service.enumerate_java_classes().ok);calls=self.runtime.adapter.calls;self.assertEqual(self.service.search_java_classes("app")[0].class_name,"com.app.A");self.assertEqual(calls,self.runtime.adapter.calls)
  self.assertEqual(self.service.enumerate_java_methods("com.app.A").value[0].overload_index,1);self.assertEqual(self.service.enumerate_java_fields("com.app.A").value[0].field_name,"x")
 def test_modules_exports_cancellation_and_stale(self):
  self.assertEqual(self.service.enumerate_native_modules().value[0].module_name,"libx.so");self.assertEqual(self.service.search_modules("/x")[0].path,"/x");self.assertEqual(self.service.enumerate_native_exports("libx.so").value[0].symbol_name,"open");self.assertEqual(self.service.search_exports("libx.so","op")[0].symbol_name,"open")
  self.assertFalse(self.service.enumerate_native_modules(Cancel()).ok);self.service.mark_stale();self.assertFalse(self.service.modules)
 def test_active_session_must_match_without_usb_fallback(self):
  self.service.select("OTHER",self.runtime.target);result=self.service.enumerate_native_modules();self.assertFalse(result.ok);self.assertIn("does not match",result.error)
