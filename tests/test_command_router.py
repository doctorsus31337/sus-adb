import tempfile
import unittest
from pathlib import Path

from app.core.command_router import CommandClassification, CommandRouter
from app.core.host_tool_resolver import HostToolResolver


class CommandRouterTests(unittest.TestCase):
    def test_adb_shell_only_is_interactive_and_serial_is_preserved(self):
        router = CommandRouter()
        plain = router.classify("adb shell")
        selected = router.classify("adb -s SERIAL shell")
        one_shot = router.classify("adb -s SERIAL shell getprop ro.product.model")
        self.assertEqual(plain.classification, CommandClassification.INTERACTIVE)
        self.assertEqual(selected.session_type, "adb-shell")
        self.assertEqual(selected.serial, "SERIAL")
        self.assertEqual(one_shot.classification, CommandClassification.ONE_SHOT)

    def test_objection_frida_and_trace_route_to_sessions(self):
        router = CommandRouter()
        objection = router.classify("objection -S socket -n org.example.app start")
        frida = router.classify("frida -H 127.0.0.1:27042 -n org.example.app")
        trace = router.classify("frida-trace -H 127.0.0.1:27042 -p 42")
        self.assertEqual(objection.session_type, "objection")
        self.assertEqual(objection.target, "org.example.app")
        self.assertEqual(frida.session_type, "frida-repl")
        self.assertEqual(trace.session_type, "frida-trace")
        self.assertTrue(all(route.opens_session for route in (objection, frida, trace)))

    def test_finite_commands_remain_in_console(self):
        router = CommandRouter()
        expected = {
            "adb devices -l": CommandClassification.ONE_SHOT,
            "adb install app.apk": CommandClassification.STREAMING_FINITE,
            "adb logcat -d": CommandClassification.STREAMING_FINITE,
            "frida-ps -ai": CommandClassification.ONE_SHOT,
            "objection version": CommandClassification.ONE_SHOT,
        }
        for command, classification in expected.items():
            with self.subTest(command=command):
                self.assertEqual(router.classify(command).classification, classification)

    def test_live_logcat_and_host_shell_do_not_block_console(self):
        router = CommandRouter()
        self.assertTrue(router.classify("adb logcat").opens_session)
        self.assertTrue(router.classify("bash").opens_session)
        self.assertEqual(
            router.classify("bash -c 'printf ok'").classification,
            CommandClassification.ONE_SHOT,
        )

    def test_resolution_preserves_executable_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="session tools ") as directory:
            executable = Path(directory) / "adb"
            executable.touch()
            resolver = HostToolResolver({"adb": str(executable)}, which=lambda _name: None)
            route = CommandRouter(resolver).classify("adb -s SERIAL shell")
            self.assertEqual(route.resolved_argv[0], str(executable.resolve()))
            self.assertEqual(route.resolved_argv[1:], ("-s", "SERIAL", "shell"))

    def test_malformed_and_unknown_commands_are_bounded(self):
        router = CommandRouter()
        malformed = router.classify("adb '")
        unknown = router.classify("mystery-tool --do-something")
        self.assertEqual(malformed.classification, CommandClassification.UNSUPPORTED)
        self.assertEqual(unknown.classification, CommandClassification.AMBIGUOUS)
        self.assertTrue(malformed.reason)
        self.assertTrue(unknown.reason)
