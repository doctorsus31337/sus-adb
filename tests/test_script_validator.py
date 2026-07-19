import unittest

from app.core.script_descriptor import ScriptDescriptor, ScriptKind
from app.core.script_validator import ScriptValidator


class ScriptValidatorTests(unittest.TestCase):
    def descriptor(self, path="agent.js", digest=""):
        return ScriptDescriptor("id", "Agent", ScriptKind.FRIDA, path, sha256=digest)
    def test_empty_typescript_size_digest_and_placeholders(self):
        self.assertFalse(ScriptValidator().validate(self.descriptor(), "").valid)
        self.assertFalse(ScriptValidator().validate(self.descriptor("agent.ts"), "let x = 1").valid)
        self.assertFalse(ScriptValidator(max_size=2).validate(self.descriptor(), "long").valid)
        result = ScriptValidator().validate(self.descriptor(digest="0" * 64), "send('${TARGET}')")
        self.assertTrue(any("digest" in item for item in result.warnings)); self.assertTrue(any("placeholder" in item for item in result.warnings))
    def test_java_send_recv_rpc_and_state_change_detection(self):
        result = ScriptValidator().validate(self.descriptor(), "Java.perform(()=>{}); send(1); recv('x',()=>{}); rpc.exports={x(){}}; Interceptor.attach(ptr('1'),{});")
        self.assertIn("rpc.exports", result.features); self.assertIn("send", result.features); self.assertIn("recv", result.features); self.assertTrue(result.changes_runtime)
        self.assertTrue(result.valid); self.assertEqual((), result.errors)
        self.assertTrue(any("Java.available" in item for item in result.warnings))
    def test_java_available_advice_is_warning_only(self):
        source = "Java.perform(function () { console.log('ready'); });"
        result = ScriptValidator().validate(self.descriptor(), source)
        self.assertTrue(result.valid); self.assertEqual((), result.errors)
        self.assertIn("Java APIs are used without checking Java.available.", result.warnings)
    def test_injected_compiler_never_needs_device(self):
        result = ScriptValidator(lambda _source: (_ for _ in ()).throw(ValueError("syntax"))).validate(self.descriptor(), "send(1)")
        self.assertFalse(result.valid); self.assertIn("syntax", result.errors[0])
