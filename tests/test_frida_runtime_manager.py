import tempfile
import unittest
from types import SimpleNamespace

from app.core.frida_python_adapter import FridaPythonAdapter
from app.core.frida_runtime_manager import FridaRuntimeManager, RuntimeState
from app.core.frida_target import FridaTarget, TargetType
from app.core.script_descriptor import ScriptDescriptor, ScriptKind, TrustState
from app.core.script_library import ScriptLibrary
from app.core.script_validator import ScriptValidator
from test_frida_python_adapter import Frida


class FridaRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.library=ScriptLibrary(self.temp.name); self.events=[]
        self.runtime=FridaRuntimeManager(FridaPythonAdapter(lambda: Frida()),self.library,ScriptValidator(),self.events.append)
        self.target=FridaTarget("App","com.app",123,TargetType.APPLICATION,True)
    def tearDown(self): self.temp.cleanup()
    def script(self,name,trust=TrustState.TRUSTED_LOCAL,changing=False):
        result=self.library.create(name,"rpc.exports={echo(v){return v;}}; send('ready');"); item=result.descriptor
        item=ScriptDescriptor(item.script_id,item.name,ScriptKind.FRIDA,item.path,trust=trust,changes_runtime=changing,sha256=item.sha256,metadata_path=item.metadata_path); return item
    def test_attach_load_multiple_duplicate_messages_rpc_post_reload_unload_detach(self):
        self.assertTrue(self.runtime.attach("serial",self.target).ok)
        one,two=self.script("one"),self.script("two"); self.assertTrue(self.runtime.load_script(one).ok); self.assertTrue(self.runtime.load_script(two).ok)
        self.assertEqual(len(self.runtime.loaded),2); self.assertIn("already",self.runtime.load_script(one).warning)
        record=self.runtime.loaded[one.script_id]; record.handle.callback({"type":"send","payload":{"x":1}},None); record.handle.callback({"type":"error","description":"bad","lineNumber":7,"stack":"trace"},None); record.handle.callback({"type":"send"},b"abc")
        self.assertTrue(self.runtime.post(one.script_id,{"ping":1}).ok); self.assertTrue(self.runtime.call_rpc(one.script_id,"echo",["ok"]).ok)
        self.assertTrue(self.runtime.reload_script(one.script_id,confirm_untrusted=True,confirm_state_change=True).ok)
        self.assertTrue(all(item.ok for item in self.runtime.unload_all())); self.assertTrue(self.runtime.detach().ok); self.assertEqual(self.runtime.state,RuntimeState.DETACHED)
        self.assertTrue(any(event.source_line==7 for event in self.events)); self.assertTrue(any(event.binary==b"abc" for event in self.events))
    def test_spawn_resume_confirmation_disconnect_and_missing_runtime(self):
        self.assertTrue(self.runtime.spawn("serial",self.target).ok); self.assertEqual(self.runtime.state,RuntimeState.SPAWNED_PAUSED); self.assertTrue(self.runtime.resume().ok)
        untrusted=self.script("u",TrustState.UNTRUSTED); self.assertFalse(self.runtime.load_script(untrusted).ok); self.assertTrue(self.runtime.load_script(untrusted,confirm_untrusted=True).ok)
        changing=self.script("c",changing=True); self.assertFalse(self.runtime.load_script(changing).ok)
        self.assertTrue(self.runtime.device_disconnected().ok)
        missing=FridaRuntimeManager(FridaPythonAdapter(lambda: (_ for _ in ()).throw(ImportError("missing"))),self.library,ScriptValidator()); self.assertFalse(missing.readiness("s",self.target).ok)

    def test_version_mismatch_is_a_warning(self):
        diagnosis = SimpleNamespace(server_running=True, port_27042=True, server_version="15.0.0", versions_match=False)
        runtime = FridaRuntimeManager(FridaPythonAdapter(lambda: Frida()), self.library, ScriptValidator(), diagnosis_provider=lambda _serial: diagnosis)
        result = runtime.readiness("serial", self.target)
        self.assertTrue(result.ok); self.assertIn("does not match", result.warning)
