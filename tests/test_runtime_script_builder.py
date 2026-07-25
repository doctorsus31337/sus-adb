import math,unittest
from app.core.runtime_explorer_models import HookTarget,RuntimeHookSpec
from app.core.runtime_script_builder import RuntimeScriptBuilder

class RuntimeScriptBuilderTests(unittest.TestCase):
 def setUp(self):self.builder=RuntimeScriptBuilder()
 def spec(self,**kw):
  data=dict(target_type=HookTarget.JAVA_METHOD,owner_name="com.app.C",member_name="run",overload=("int",),selected_target="com.app",generated_script_name="observe-run");data.update(kw);return RuntimeHookSpec(**data)
 def test_java_observation_deterministic_and_portable(self):
  a=self.builder.build(self.spec(hook_id="same"));b=self.builder.build(self.spec(hook_id="same"));self.assertTrue(a.ok);self.assertEqual(a.source,b.source);self.assertEqual(a.filename,b.filename);self.assertFalse(a.descriptor.changes_runtime);self.assertFalse(a.descriptor.path.startswith("/"));self.assertIn("original.apply",a.source)
 def test_native_observation_and_validation(self):
  result=self.builder.build(RuntimeHookSpec(HookTarget.NATIVE_EXPORT,"libx.so","open",selected_target="com.app"));self.assertTrue(result.ok);self.assertIn("Interceptor.attach",result.source)
  self.assertFalse(self.builder.build(self.spec(overload=())).ok);self.assertFalse(self.builder.build(self.spec(owner_name="bad class")).ok)
 def test_argument_and_return_replacement(self):
  changing=dict(changes_runtime=True,modification_settings={"mode":"replace-argument","argumentIndex":0,"value":{"x":[1,True,None]}})
  result=self.builder.build(self.spec(**changing));self.assertTrue(result.ok);self.assertTrue(result.descriptor.changes_runtime);self.assertIn("state-changing",result.source)
  result=self.builder.build(self.spec(changes_runtime=True,modification_settings={"mode":"replace-return","value":"ok"}));self.assertTrue(result.ok)
  result=self.builder.build(self.spec(changes_runtime=True,modification_settings={"mode":"throw-exception","exceptionClass":"java.lang.IllegalStateException","message":"test"}));self.assertTrue(result.ok);self.assertIn("throw-exception",result.source)
  self.assertFalse(self.builder.build(self.spec(changes_runtime=True,modification_settings={"mode":"throw-exception","exceptionClass":"evil.Exception"})).ok)
  self.assertFalse(self.builder.build(self.spec(changes_runtime=True,modification_settings={"mode":"replace-return","value":math.nan})).ok)
  self.assertFalse(self.builder.build(self.spec(changes_runtime=False,modification_settings={"mode":"replace-return","value":1})).ok)
