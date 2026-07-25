import unittest
from types import SimpleNamespace

from app.core.frida_runtime_manager import RuntimeResult
from app.core.script_descriptor import ScriptDescriptor, ScriptKind, TrustState
from app.core.script_profile import FailurePolicy, ScriptProfile, ScriptStage
from app.core.script_profile_runner import ScriptProfileRunner


class Runtime:
    def __init__(self, failures=()): self.calls=[]; self.failures=set(failures)
    def load_script(self, item, **_kwargs): self.calls.append(item.script_id); return RuntimeResult(item.script_id not in self.failures, error="failed" if item.script_id in self.failures else None)
    def unload_script(self, item): self.calls.append("unload:" + item); return RuntimeResult(True)


class ScriptProfileRunnerTests(unittest.TestCase):
    def scripts(self): return {key: ScriptDescriptor(key, key, ScriptKind.FRIDA, key + ".js", trust=TrustState.TRUSTED_LOCAL) for key in "abc"}
    def test_missing_and_untrusted_confirmation(self):
        runtime=Runtime(); runner=ScriptProfileRunner(runtime); scripts=self.scripts(); scripts["a"] = ScriptDescriptor("a", "a", "frida", "a.js")
        self.assertFalse(runner.validate(ScriptProfile("x", stages=(ScriptStage("missing"),)), scripts).ok)
        self.assertFalse(runner.validate(ScriptProfile("x", stages=(ScriptStage("a"),)), scripts).ok)
    def test_order_stop_continue_cancel_and_unload(self):
        scripts=self.scripts(); runtime=Runtime(("b",)); runner=ScriptProfileRunner(runtime)
        profile=ScriptProfile("x", stages=(ScriptStage("a"), ScriptStage("b", failure_policy=FailurePolicy.CONTINUE), ScriptStage("c")))
        result=runner.run(profile, scripts); self.assertEqual(runtime.calls, ["a","b","c"]); self.assertFalse(result.ok)
        runner.unload(); self.assertIn("unload:a", runtime.calls)
        runner.cancel(); self.assertTrue(runner.cancelled)
    def test_stop_on_failure(self):
        runtime=Runtime(("b",)); runner=ScriptProfileRunner(runtime); runner.run(ScriptProfile("x", stages=(ScriptStage("a"),ScriptStage("b"),ScriptStage("c"))), self.scripts()); self.assertEqual(runtime.calls,["a","b"])
