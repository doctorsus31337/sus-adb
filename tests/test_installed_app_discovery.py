import unittest

from app.core.command_result import CommandResult
from app.core.installed_app_discovery import (
    ADBInstalledAppDiscovery,
    filter_installed_apps,
)


class FakeADB:
    def __init__(self):
        self.calls = []

    def run(self, *args, serial=None, timeout=None):
        self.calls.append((args, serial, timeout))
        command = " ".join(args)
        if "list packages -f" in command:
            output = "\n".join((
                "package:/data/app/Example Base/base.apk=com.example.app uid:10123 versionCode:7",
                "package:/system/priv-app/System/System.apk=com.android.system uid:1000 versionCode:42",
                "vendor variation ignored",
            ))
        elif "list packages -d" in command:
            output = "package:com.android.system"
        elif "query-activities" in command:
            output = "com.example.app/.MainActivity"
        elif "ps -A" in command:
            output = "PID NAME\n321 com.example.app:worker\n"
        else:
            output = ""
        return CommandResult.from_command(args, 0, stdout=output)


class InstalledAppDiscoveryTests(unittest.TestCase):
    def test_scan_uses_only_explicit_serial_and_needs_no_frida(self):
        adb = FakeADB()
        result = ADBInstalledAppDiscovery(adb).scan("SERIAL WITH SPACE")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.applications), 2)
        self.assertTrue(all(call[1] == "SERIAL WITH SPACE" for call in adb.calls))
        example = next(
            app for app in result.applications
            if app.package_id == "com.example.app"
        )
        self.assertFalse(example.system)
        self.assertTrue(example.launchable)
        self.assertTrue(example.running)
        self.assertEqual(example.pid, 321)
        system = next(app for app in result.applications if app.system)
        self.assertFalse(system.enabled)

    def test_no_serial_is_an_explained_empty_state(self):
        adb = FakeADB()
        result = ADBInstalledAppDiscovery(adb).scan(None)
        self.assertFalse(result.ok)
        self.assertIn("No device", result.errors[0])
        self.assertFalse(adb.calls)

    def test_filters_are_local_and_composable(self):
        apps = ADBInstalledAppDiscovery(FakeADB()).scan("SERIAL").applications
        self.assertEqual(
            [app.package_id for app in filter_installed_apps(apps, "example")],
            ["com.example.app"],
        )
        self.assertEqual(len(filter_installed_apps(apps, system_only=True)), 1)
        self.assertEqual(len(filter_installed_apps(
            apps, user_only=True, launchable_only=True, running_only=True
        )), 1)

    def test_parser_accepts_virtualized_apk_paths(self):
        parsed = ADBInstalledAppDiscovery.parse_package_line(
            "package:/data/app/~~abc==/base.apk=org.example uid:10001"
        )
        self.assertEqual(parsed[1], "org.example")


if __name__ == "__main__":
    unittest.main()
