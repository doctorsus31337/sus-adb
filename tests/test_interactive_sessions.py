import tempfile
import unittest
from pathlib import Path

from app.core.command_result import CommandResult
from app.core.command_router import CommandRouter
from app.core.external_terminal import ExternalLaunch
from app.core.frida_target import FridaTarget, TargetType
from app.core.interactive_sessions import (
    InteractiveSessionManager,
    InteractiveSessionState,
    InteractiveSessionType,
)
from app.core.objection_session_recovery import ObjectionSessionRecovery


class Resolver:
    paths = {
        "adb": "/opt/tools/adb",
        "objection": "/opt/tools/objection",
        "frida": "/opt/tools/frida",
        "frida-trace": "/opt/tools/frida-trace",
        "bash": "/bin/bash",
    }

    def resolve(self, name):
        return self.paths.get(name)

    def missing_message(self, name, *_args):
        return f"{name} is missing"


class Process:
    def __init__(self):
        self.signal = None
        self.terminated = False
        self.returncode = None

    def send_signal(self, value):
        self.signal = value

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def poll(self):
        return self.returncode


class Terminal:
    def __init__(self):
        self.commands = []
        self.processes = []
        self.fail = False

    def launch_tracked(self, command, *, title):
        self.commands.append((tuple(command), title))
        if self.fail:
            return ExternalLaunch(
                CommandResult.from_command(command, -1, error="launch failed"),
                backend="fixture",
            )
        process = Process()
        self.processes.append(process)
        return ExternalLaunch(
            CommandResult.from_command(command, 0, stdout="launched"),
            process,
            "fixture-terminal",
        )


class Objection:
    objection_path = "/opt/tools/objection"

    def build_attach_command(self, target, transport, serial):
        return (self.objection_path, "-S", transport, "-n", target, "start")

    def build_spawn_command(self, target, transport, serial):
        return (self.objection_path, "-S", transport, "-n", target, "-s", "start")


class FridaSessions:
    frida_path = "/opt/tools/frida"
    frida_trace_path = "/opt/tools/frida-trace"


class RecoveryFrida:
    def managed_forwarding_ports(self, _serial):
        return ()


class InteractiveSessionTests(unittest.TestCase):
    def manager(self, selected=None, singleton=()):
        selected = selected or {"value": "SERIAL"}
        terminal = Terminal()
        manager = InteractiveSessionManager(
            terminal,
            Resolver(),
            selected_serial_provider=lambda: selected["value"],
            adb_path_provider=lambda: "/opt/tools/adb",
            objection_manager=Objection(),
            frida_sessions=FridaSessions(),
            clock=lambda: "2026-07-24T12:00:00+00:00",
            id_factory=lambda: f"session-{len(terminal.commands) + 1}",
            singleton_types=singleton,
        )
        return manager, terminal, selected

    def target(self):
        return FridaTarget(
            "Fixture App", "org.example.fixture", 42, TargetType.APPLICATION, True
        )

    def test_adb_and_root_shell_require_explicit_selected_serial(self):
        manager, _terminal, _selected = self.manager()
        shell = manager.build_adb_shell("SERIAL")
        self.assertTrue(shell.ready)
        self.assertEqual(shell.command, ("/opt/tools/adb", "-s", "SERIAL", "shell"))
        self.assertTrue(Path(shell.executable).is_absolute())
        self.assertFalse(manager.build_adb_shell("").ready)
        self.assertFalse(
            manager.build_adb_shell(
                "SERIAL", root=True, root_available=False, root_confirmed=True
            ).ready
        )
        root = manager.build_adb_shell(
            "SERIAL", root=True, root_available=True, root_confirmed=True
        )
        self.assertEqual(root.session_type, InteractiveSessionType.ROOT_SHELL)
        self.assertEqual(root.command[-1], "su")

    def test_objection_attach_and_spawn_preserve_target_and_serial(self):
        manager, _terminal, _selected = self.manager()
        attach = manager.build_objection("SERIAL", "org.example.fixture")
        spawn = manager.build_objection("SERIAL", "org.example.fixture", spawn=True)
        self.assertTrue(attach.ready)
        self.assertEqual(attach.attach_mode, "attach")
        self.assertEqual(spawn.attach_mode, "spawn")
        self.assertIn("-s", spawn.command)
        self.assertEqual(spawn.serial, "SERIAL")
        self.assertEqual(spawn.target, "org.example.fixture")

    def test_frida_attach_spawn_pid_trace_and_script_path_with_spaces(self):
        manager, _terminal, _selected = self.manager()
        with tempfile.TemporaryDirectory(prefix="script library ") as directory:
            script = Path(directory) / "my script.js"
            script.write_text("send('ok');", encoding="utf-8")
            attach = manager.build_frida(
                "SERIAL", self.target(), mode="attach", script_path=str(script)
            )
            spawn = manager.build_frida("SERIAL", self.target(), mode="spawn")
            pid = manager.build_frida("SERIAL", self.target(), mode="pid")
            trace = manager.build_frida(
                "SERIAL", self.target(), trace=True, trace_pattern="open*"
            )
            self.assertTrue(all(plan.ready for plan in (attach, spawn, pid, trace)))
            self.assertEqual(attach.command[-2:], ("-l", str(script.resolve())))
            self.assertIn("-f", spawn.command)
            self.assertIn("-p", pid.command)
            self.assertEqual(trace.session_type, InteractiveSessionType.FRIDA_TRACE)
            self.assertIn("-i", trace.command)
            self.assertTrue(Path(attach.command[0]).is_absolute())

    def test_console_route_inserts_serial_and_rejects_silent_switch(self):
        manager, _terminal, _selected = self.manager()
        router = CommandRouter(Resolver())
        inserted = manager.plan_from_route(
            router.classify("adb shell"), "SERIAL", self.target()
        )
        mismatch = manager.plan_from_route(
            router.classify("adb -s OTHER shell"), "SERIAL", self.target()
        )
        self.assertEqual(inserted.command, ("/opt/tools/adb", "-s", "SERIAL", "shell"))
        self.assertTrue(inserted.ready)
        self.assertFalse(mismatch.ready)
        self.assertIn("does not match", mismatch.errors[-1])

    def test_console_objection_and_frida_routes_preserve_advanced_argv(self):
        manager, _terminal, _selected = self.manager()
        router = CommandRouter(Resolver())
        objection = manager.plan_from_route(
            router.classify(
                "objection -S socket -n org.example.fixture -s start"
            ),
            "SERIAL",
            self.target(),
        )
        frida = manager.plan_from_route(
            router.classify(
                "frida -H 10.0.0.2:27042 -n org.example.fixture --runtime v8"
            ),
            "SERIAL",
            self.target(),
        )
        self.assertTrue(objection.ready)
        self.assertEqual(objection.attach_mode, "spawn")
        self.assertIn("--runtime", frida.command)
        self.assertEqual(frida.command[0], "/opt/tools/frida")

    def test_launch_lifecycle_diagnostics_interrupt_terminate_and_close(self):
        manager, terminal, _selected = self.manager()
        states = []
        manager.subscribe(lambda record: states.append(record.state))
        result = manager.launch(manager.build_adb_shell("SERIAL"))
        self.assertTrue(result.ok)
        self.assertEqual(result.record.prompt_ready_time, "")
        self.assertEqual(
            states[:3],
            [
                InteractiveSessionState.PREPARING,
                InteractiveSessionState.LAUNCHING,
                InteractiveSessionState.CONNECTED,
            ],
        )
        self.assertIn("SERIAL", manager.diagnostics(result.record.session_id))
        self.assertIn("Launch stages:", manager.diagnostics(result.record.session_id))
        interrupted = manager.interrupt(result.record.session_id)
        self.assertTrue(interrupted.ok)
        self.assertIsNotNone(terminal.processes[0].signal)
        terminated = manager.terminate(result.record.session_id)
        self.assertTrue(terminated.ok)
        self.assertTrue(terminal.processes[0].terminated)
        self.assertTrue(manager.close_record(result.record.session_id).ok)
        self.assertFalse(manager.list())

    def test_reconnect_requires_same_serial_and_shutdown_cleans_all(self):
        manager, terminal, selected = self.manager()
        launched = manager.launch(manager.build_adb_shell("SERIAL"))
        selected["value"] = "OTHER"
        self.assertFalse(manager.reconnect(launched.record.session_id).ok)
        selected["value"] = "SERIAL"
        reconnected = manager.reconnect(launched.record.session_id)
        self.assertTrue(reconnected.ok)
        manager.shutdown()
        self.assertTrue(all(process.terminated for process in terminal.processes))

    def test_singleton_is_configurable_per_type_and_target(self):
        manager, terminal, _selected = self.manager(singleton=("adb-shell",))
        plan = manager.build_adb_shell("SERIAL")
        first = manager.launch(plan)
        second = manager.launch(plan)
        self.assertEqual(first.record.session_id, second.record.session_id)
        self.assertEqual(len(terminal.commands), 1)

    def test_launch_failure_is_recorded_without_process(self):
        manager, terminal, _selected = self.manager()
        terminal.fail = True
        result = manager.launch(manager.build_adb_shell("SERIAL"))
        self.assertFalse(result.ok)
        self.assertEqual(result.record.state, InteractiveSessionState.FAILED)
        self.assertEqual(result.record.last_error, "launch failed")

    def test_objection_external_backend_reports_unobservable_prompt_stages(self):
        manager, _terminal, _selected = self.manager()
        result = manager.launch(
            manager.build_objection("SERIAL", "org.example.fixture")
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.record.prompt_ready_time, "")
        stages = dict(result.record.stages)
        self.assertEqual(stages["Frida connection"], "Observe in external terminal")
        self.assertEqual(stages["agent load"], "Observe in external terminal")
        self.assertEqual(stages["prompt ready"], "Not observable by external backend")

    def test_objection_device_gone_is_actionable_bounded_and_preserves_history(self):
        manager, _terminal, selected = self.manager()
        manager.objection_recovery = ObjectionSessionRecovery(
            RecoveryFrida(),
            selected_serial_provider=lambda: selected["value"],
            adb_state_provider=lambda _serial: "device",
        )
        launched = manager.launch(
            manager.build_objection("SERIAL", "org.example.fixture")
        )
        report = None
        for _index in range(20):
            report = manager.report_objection_failure(
                launched.record.session_id,
                "frida.InvalidOperationError: device is gone\n"
                "Unable to run cleanups: script is destroyed",
                command_history=("help", "help android sslpinning"),
            )
        record = manager.records[launched.record.session_id]
        self.assertEqual(record.state, InteractiveSessionState.DISCONNECTED)
        self.assertEqual(record.command_history[-1], "help android sslpinning")
        self.assertEqual(report.repeat_count, 20)
        self.assertLessEqual(len(record.diagnostics), 12)
        self.assertIn("Technical Details:", manager.diagnostics(record.session_id))


if __name__ == "__main__":
    unittest.main()
