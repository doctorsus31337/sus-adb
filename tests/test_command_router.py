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

    def test_fastboot_is_validated_before_generic_registry_fallback(self):
        router = CommandRouter()
        allowed = (
            "fastboot --version",
            "fastboot help",
            "fastboot devices",
            "fastboot devices -l",
            "fastboot -s FB-SERIAL getvar product",
            "fastboot --serial FB-SERIAL getvar all",
        )
        for command in allowed:
            with self.subTest(command=command):
                route = router.classify(command)
                self.assertEqual(route.classification, CommandClassification.ONE_SHOT)
        blocked = (
            "fastboot flash boot boot.img",
            "fastboot erase userdata",
            "fastboot reboot",
            "fastboot oem fixture",
            "fastboot mystery",
        )
        for command in blocked:
            with self.subTest(command=command):
                route = router.classify(command)
                self.assertEqual(route.classification, CommandClassification.UNSUPPORTED)
                self.assertIn("not supported", route.reason)

    def test_command_typography_is_rejected_before_registry_fallback(self):
        router = CommandRouter()
        for command in (
            "fastboot\u00a0--version",
            "fastboot \u2013\u2013version",
            "fastboot \u2014\u2014version",
            "fastboot \u2011\u2011version",
            "fastboot\u200b --version",
            "fastboot \u2212\u2212version",
        ):
            with self.subTest(command=repr(command)):
                route = router.classify(command)
                self.assertEqual(
                    route.classification, CommandClassification.UNSUPPORTED
                )
                self.assertIn("non-ASCII punctuation", route.reason)
                self.assertIn("fastboot --version", route.reason)
                self.assertNotIn("supported command registry", route.reason)

    def test_exact_ascii_fastboot_version_remains_one_shot(self):
        route = CommandRouter().classify("fastboot --version")
        self.assertEqual(route.classification, CommandClassification.ONE_SHOT)
        self.assertEqual(route.argv, ("fastboot", "--version"))

    def test_fastboot_serial_has_distinct_route_context(self):
        route = CommandRouter().classify(
            "fastboot --serial FB-SERIAL getvar current-slot"
        )
        self.assertEqual(route.fastboot_serial, "FB-SERIAL")
        self.assertEqual(route.serial, "")

    def test_fastboot_exe_normalizes_and_configured_space_path_is_one_token(self):
        with tempfile.TemporaryDirectory(prefix="fastboot tools ") as directory:
            executable = Path(directory) / "fastboot.exe"
            executable.touch()
            resolver = HostToolResolver(
                {"fastboot": str(executable)},
                which=lambda _name: None,
                platform_name="nt",
            )
            route = CommandRouter(resolver, platform_name="nt").classify(
                "fastboot.exe --serial FB-SERIAL getvar product"
            )
            self.assertEqual(route.classification, CommandClassification.ONE_SHOT)
            self.assertEqual(route.resolved_argv[0], str(executable.resolve()))
            self.assertEqual(
                route.resolved_argv[1:],
                ("--serial", "FB-SERIAL", "getvar", "product"),
            )

    def test_platform_tools_additions_are_explicitly_finite(self):
        router = CommandRouter()
        for command in (
            "adb version",
            "adb host-features",
            "adb features",
            "adb mdns services",
            "adb connect 192.0.2.10:5555",
            "adb connect device.example:5037",
            "adb disconnect",
            "adb disconnect device.example:5037",
            "adb reconnect device",
            "adb reconnect offline",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    router.classify(command).classification,
                    CommandClassification.ONE_SHOT,
                )

    def test_adb_connection_endpoints_are_locally_validated(self):
        router = CommandRouter()
        for command in (
            "adb connect missing-port",
            "adb connect host:0",
            "adb connect host:65536",
            "adb connect 999.999.999.999:5555",
            "adb connect https://host:5555",
            "adb connect user@host:5555",
            "adb connect host:5555/path",
            "adb connect 'host name:5555'",
            "adb connect host:5555 extra",
            "adb disconnect host:abc",
            "adb disconnect host:5555 extra",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    router.classify(command).classification,
                    CommandClassification.UNSUPPORTED,
                )

    def test_adb_pair_is_deferred_and_never_routable(self):
        route = CommandRouter().classify("adb pair host:37123 123456")
        self.assertEqual(route.classification, CommandClassification.UNSUPPORTED)
        self.assertIn("dedicated Wireless ADB pairing workflow", route.reason)

    def test_unrelated_unknown_adb_behavior_is_not_changed(self):
        route = CommandRouter().classify("adb legacy-unknown fixture")
        self.assertEqual(route.classification, CommandClassification.ONE_SHOT)

    def test_malformed_and_unknown_commands_are_bounded(self):
        router = CommandRouter()
        malformed = router.classify("adb '")
        unknown = router.classify("mystery-tool --do-something")
        self.assertEqual(malformed.classification, CommandClassification.UNSUPPORTED)
        self.assertEqual(unknown.classification, CommandClassification.AMBIGUOUS)
        self.assertTrue(malformed.reason)
        self.assertTrue(unknown.reason)
