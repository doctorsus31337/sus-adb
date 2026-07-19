import unittest

from app.core.frida_python_adapter import FridaPythonAdapter


class Exports:
    def echo(self, value): return value
class Script:
    def __init__(self): self.exports_sync = Exports(); self.callback = None; self.loaded = False
    def on(self, _name, callback): self.callback = callback
    def load(self): self.loaded = True
    def unload(self): self.loaded = False
    def post(self, message, data=None): self.posted = (message, data)
class Session:
    def create_script(self, _source): return Script()
    def detach(self): self.detached = True
class Device:
    def attach(self, target): self.attached = target; return Session()
    def spawn(self, argv): self.spawned = argv; return 42
    def resume(self, pid): self.resumed = pid
class Manager:
    def add_remote_device(self, endpoint): self.endpoint = endpoint; return Device()
class Frida:
    __version__ = "16.7.0"
    def __init__(self): self.manager = Manager()
    def get_device_manager(self): return self.manager


class FridaPythonAdapterTests(unittest.TestCase):
    def test_missing_module_is_structured(self):
        adapter = FridaPythonAdapter(lambda: (_ for _ in ()).throw(ImportError("missing")))
        self.assertEqual(adapter.availability().error_code, "module-missing")

    def test_remote_attach_spawn_resume_script_post_rpc_and_detach(self):
        module = Frida(); adapter = FridaPythonAdapter(lambda: module)
        device = adapter.acquire_device().value; self.assertEqual(module.manager.endpoint, "127.0.0.1:27042")
        session = adapter.attach(device, 12).value; self.assertEqual(device.attached, 12)
        pid = adapter.spawn(device, "com.test").value; adapter.resume(device, pid); self.assertEqual(device.resumed, 42)
        script = adapter.create_script(session, "send(1)").value; messages = []
        adapter.register_message_callback(script, messages.append); adapter.load_script(script); adapter.post(script, {"x": 1})
        self.assertIn("echo", adapter.list_exports(script).value); self.assertEqual(adapter.call_export(script, "echo", ["ok"]).value, "ok")
        self.assertEqual(adapter.call_export(script, "missing").error_code, "rpc-export-missing")
        adapter.unload_script(script); self.assertTrue(adapter.detach(session).ok)
