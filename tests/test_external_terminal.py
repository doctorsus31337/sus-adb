import unittest
import subprocess

from app.core.external_terminal import ExternalTerminal


class ExternalTerminalTests(unittest.TestCase):
    def build_for(self, terminal_name):
        which = lambda name: f"/usr/bin/{name}" if name == terminal_name else None
        return ExternalTerminal(
            which=which, launcher=lambda _command, **_kwargs: object(),
            platform_name="posix", realpath=lambda path: path,
        )

    def test_each_linux_terminal_command_form(self):
        expected_flags = {
            "x-terminal-emulator": "-e",
            "konsole": "--separate",
            "gnome-terminal": "--",
            "xfce4-terminal": "-x",
            "kitty": "-e",
            "alacritty": "-e",
        }
        for name, flag in expected_flags.items():
            with self.subTest(name=name):
                result = self.build_for(name).build_command(("frida", "-n", "App Name"))
                self.assertTrue(result.ok)
                if name == "konsole":
                    self.assertEqual(
                        result.command,
                        ("/usr/bin/konsole", "--separate", "--hold", "-e", "frida", "-n", "App Name"),
                    )
                else:
                    self.assertEqual(result.command, (f"/usr/bin/{name}", flag, "frida", "-n", "App Name"))

    def test_windows_powershell_quotes_space_and_apostrophe(self):
        terminal = ExternalTerminal(
            which=lambda name: "C:/PowerShell.exe" if name == "powershell" else None,
            launcher=lambda _command, **_kwargs: object(), platform_name="nt",
        )
        result = terminal.build_command(("frida", "-n", "Doctor's App"))
        self.assertEqual(result.command[:3], ("C:/PowerShell.exe", "-NoExit", "-Command"))
        self.assertIn("'Doctor''s App'", result.command[3])

    def test_windows_terminal_is_preferred_and_preserves_space_arguments(self):
        terminal = ExternalTerminal(
            which=lambda name: "C:/Program Files/WindowsApps/wt.exe" if name == "wt.exe" else None,
            launcher=lambda _command, **_kwargs: object(), platform_name="nt",
        )
        result = terminal.build_command(
            ("C:/Program Files/Frida/frida.exe", "-l", "C:/My Scripts/test.js")
        )
        self.assertEqual(
            result.command,
            (
                "C:/Program Files/WindowsApps/wt.exe", "new-tab", "--title",
                "SUS Companion Session", "C:/Program Files/Frida/frida.exe",
                "-l", "C:/My Scripts/test.js",
            ),
        )

    def test_windows_cmd_is_last_fallback(self):
        terminal = ExternalTerminal(
            which=lambda name: "C:/Windows/System32/cmd.exe" if name == "cmd.exe" else None,
            launcher=lambda _command, **_kwargs: object(), platform_name="nt",
        )
        result = terminal.build_command(("C:/Tools/adb.exe", "-s", "SERIAL", "shell"))
        self.assertEqual(result.command[:2], ("C:/Windows/System32/cmd.exe", "/K"))
        self.assertIn("SERIAL", result.command[2])

    def test_missing_terminal_is_structured(self):
        result = ExternalTerminal(which=lambda _name: None, platform_name="posix").build_command(("frida",))
        self.assertFalse(result.ok)
        self.assertIn("terminal", result.error.lower())

    def test_launch_uses_injected_launcher_and_detached_posix_options(self):
        launched = []
        launch_options = []
        terminal = ExternalTerminal(
            which=lambda name: "/usr/bin/kitty" if name == "kitty" else None,
            launcher=lambda command, **kwargs: (launched.append(command), launch_options.append(kwargs)),
            platform_name="posix", realpath=lambda path: path,
        )
        result = terminal.launch(("frida", "-n", "App Name"))
        self.assertTrue(result.ok)
        self.assertEqual(launched[0][-1], "App Name")
        self.assertIs(launch_options[0]["stdout"], subprocess.DEVNULL)
        self.assertIs(launch_options[0]["stderr"], subprocess.DEVNULL)
        self.assertTrue(launch_options[0]["start_new_session"])

    def test_tracked_launch_returns_process_and_backend(self):
        process = object()
        terminal = ExternalTerminal(
            which=lambda name: "/usr/bin/konsole" if name == "konsole" else None,
            launcher=lambda _command, **_kwargs: process,
            platform_name="posix", realpath=lambda path: path,
        )
        launched = terminal.launch_tracked(("adb", "-s", "SERIAL", "shell"))
        self.assertTrue(launched.result.ok)
        self.assertIs(launched.process, process)
        self.assertEqual(launched.backend, "konsole")

    def test_x_terminal_emulator_resolving_to_konsole_uses_konsole_form(self):
        terminal = ExternalTerminal(
            which=lambda name: "/usr/bin/x-terminal-emulator" if name == "x-terminal-emulator" else None,
            launcher=lambda _command, **_kwargs: object(), platform_name="posix",
            realpath=lambda _path: "/usr/bin/konsole",
        )
        result = terminal.build_command(("frida", "-n", "App Name"))
        self.assertEqual(
            result.command,
            ("/usr/bin/x-terminal-emulator", "--separate", "--hold", "-e", "frida", "-n", "App Name"),
        )
        self.assertEqual(result.command[-3:], ("frida", "-n", "App Name"))

    def test_popen_failure_is_structured(self):
        def fail(_command, **_kwargs):
            raise OSError("terminal launch failed")

        terminal = ExternalTerminal(
            which=lambda name: "/usr/bin/kitty" if name == "kitty" else None,
            launcher=fail, platform_name="posix", realpath=lambda path: path,
        )
        result = terminal.launch(("frida", "-n", "App Name"))
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "terminal launch failed")


if __name__ == "__main__":
    unittest.main()
