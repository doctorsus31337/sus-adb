import unittest
from app.core import runtime_agent_templates as t

class RuntimeAgentTemplateTests(unittest.TestCase):
 def test_discovery_guards_and_safe_interpolation(self):
  source=t.java_member_enumeration("x.';send('bad')//")
  self.assertIn("Java.available",source);self.assertIn("rpc.exports",source);self.assertNotIn("var NAME=x.'",source)
  self.assertEqual(t.java_class_enumeration(),t.java_class_enumeration())
  self.assertIn("Process.enumerateModules",t.native_module_enumeration());self.assertIn("enumerateExports",t.native_export_enumeration("lib.so"))
 def test_observation_original_transport_stacks_and_rate_limit(self):
  options={"logArguments":True,"logReturn":True,"logExceptions":True,"javaStack":True,"nativeBacktrace":True,"rateLimit":5,"maxPreview":100}
  java=t.java_observation({"hookId":"h"},"C","m",("int",),options,{})
  self.assertIn("Java.available",java);self.assertIn(".overload.apply",java);self.assertIn("original.apply",java);self.assertIn("method-enter",java);self.assertIn("method-leave",java);self.assertIn("exception",java);self.assertIn("getStackTraceString",java);self.assertNotIn("Socket",java)
  native=t.native_observation({"hookId":"h"},"lib.so","open",options);self.assertIn("Interceptor.attach",native);self.assertIn("Thread.backtrace",native);self.assertIn("rateLimit",native);self.assertNotIn("sendTo",native)
 def test_modification_is_visibly_classified(self):
  source=t.java_observation({"hookId":"h"},"C","m",("int",),{"maxPreview":100},{"mode":"replace-return","value":False})
  self.assertIn("java-hook-state-changing",source);self.assertIn("replace-return",source)
