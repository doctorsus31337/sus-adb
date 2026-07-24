import unittest
from types import MappingProxyType, SimpleNamespace

from app.core.contextual_assistant import ContextualAssistantService
from app.core.frida_target import FridaTarget, TargetType
from app.core.interactive_sessions import SessionLaunchPlan, InteractiveSessionType


class FakeService:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def scan(self, serial):
        self.calls.append(serial)
        return SimpleNamespace(
            ok=True, serial=serial, applications=(1, 2), errors=()
        )

    def discover_combined(self, serial):
        self.calls.append(serial)
        return SimpleNamespace(ok=True, serial=serial, targets=(1,), errors=())

    def check(self, name):
        self.calls.append(name)
        return SimpleNamespace(
            installed=True, error=None, display_name=name.title(),
            version="1.2.3", executable_path=f"/tools/{name}",
        )

    def diagnose(self, serial):
        self.calls.append(serial)
        return SimpleNamespace(
            reachable=True, server_running=True, port_27042=True,
            port_27043=True, errors=(),
        )

    def scan_scripts(self):
        self.calls.append("scripts")


class FakeLibrary:
    def __init__(self):
        self.calls = 0

    def scan(self):
        self.calls += 1
        descriptor = SimpleNamespace(
            kind=SimpleNamespace(value="frida"),
            path="/safe library/my script.js",
        )
        return SimpleNamespace(ok=True, descriptors=(descriptor,), error=None)


class FakeSessions:
    def __init__(self):
        self.calls = []

    def build_frida(self, serial, target, **options):
        self.calls.append(("frida", serial, target, options))
        return SessionLaunchPlan(
            InteractiveSessionType.FRIDA_REPL,
            ("/tools with spaces/frida", "-H", options["endpoint"], "-n", target.identifier),
            serial=serial,
            target=target.identifier,
            executable="/tools with spaces/frida",
        )

    def build_objection(self, serial, target, **options):
        self.calls.append(("objection", serial, target, options))
        return SessionLaunchPlan(
            InteractiveSessionType.OBJECTION,
            ("/tools/objection", "-S", "socket", "-n", target, "start"),
            serial=serial,
            target=target,
            executable="/tools/objection",
        )

    def launch(self, plan):
        self.calls.append(("launch", plan))
        return SimpleNamespace(
            ok=True, error="", record=SimpleNamespace(session_id="session-1")
        )

    def list(self):
        return ()


class ContextualAssistantTests(unittest.TestCase):
    def service(self):
        installed = FakeService(None)
        runtime = FakeService(None)
        tools = FakeService(None)
        frida = FakeService(None)
        sessions = FakeSessions()
        library = FakeLibrary()
        selected = FridaTarget(
            "Demo", "org.example.demo", 41, TargetType.APPLICATION, True
        )
        service = ContextualAssistantService(
            installed, runtime, tools, frida, sessions, library,
            selected_target_provider=lambda: selected,
        )
        return service, installed, runtime, tools, frida, sessions, library

    def context(self):
        return SimpleNamespace(
            selected_device=MappingProxyType({
                "serial": "SERIAL-1", "display_name": "Demo Device",
            }),
            selected_target=MappingProxyType({
                "identifier": "org.example.demo", "pid": 41,
            }),
            adb_state="device",
            interface_mode="advanced",
        )

    def test_construction_and_state_mapping_perform_no_action(self):
        service, installed, runtime, tools, frida, sessions, library = self.service()
        state = service.state("frida", self.context())
        self.assertEqual(state.serial, "SERIAL-1")
        self.assertEqual(state.target, "org.example.demo")
        self.assertEqual(state.pid, 41)
        self.assertEqual(
            (installed.calls, runtime.calls, tools.calls, frida.calls, sessions.calls, library.calls),
            ([], [], [], [], [], 0),
        )

    def test_explicit_scans_and_diagnostics_bind_same_serial(self):
        service, installed, runtime, tools, frida, _, _ = self.service()
        state = service.state("frida", self.context())
        self.assertTrue(service.scan_installed(state).ok)
        self.assertTrue(service.scan_runtime(state).ok)
        self.assertTrue(service.check_tool("frida").ok)
        self.assertTrue(service.diagnose_frida(state).ok)
        self.assertEqual(installed.calls, ["SERIAL-1"])
        self.assertEqual(runtime.calls, ["SERIAL-1"])
        self.assertEqual(frida.calls, ["SERIAL-1"])
        self.assertEqual(tools.calls, ["frida"])

    def test_command_plans_use_shared_session_builder_and_copy_safe_paths(self):
        service, *_, sessions, library = self.service()
        state = service.state("frida", self.context())
        scripts = service.scripts()
        plan = service.frida_plan(
            state, mode="attach", script_path=scripts.value[0].path
        )
        objection = service.objection_plan(state, spawn=True)
        self.assertEqual(plan.serial, "SERIAL-1")
        self.assertIn("'/tools with spaces/frida'", plan.preview("posix"))
        self.assertEqual(objection.target, "org.example.demo")
        self.assertEqual(sessions.calls[0][1], "SERIAL-1")
        self.assertEqual(sessions.calls[1][1], "SERIAL-1")
        self.assertEqual(library.calls, 1)

    def test_troubleshooting_explains_help_and_connection_loss(self):
        result = ContextualAssistantService.troubleshoot(
            "objection", "device is gone"
        )
        self.assertTrue(result.ok)
        self.assertIn("same serial", result.detail)
        self.assertIn("displays reference help", result.detail)


if __name__ == "__main__":
    unittest.main()
