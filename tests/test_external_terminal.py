import unittest

from app.core.external_terminal import ExternalTerminal


class ExternalTerminalTests(unittest.TestCase):
    def build_for(self, terminal_name):
        which = lambda name: f"/usr/bin/{name}" if name == terminal_name else None
        return ExternalTerminal(which=which, launcher=lambda _command: object(), platform_name="posix")

    def test_each_linux_terminal_command_form(self):
        expected_flags = {
            "x-terminal-emulator": "-e",
            "konsole": "-e",
            "gnome-terminal": "--",
            "xfce4-terminal": "-x",
            "kitty": "-e",
            "alacritty": "-e",
        }
        for name, flag in expected_flags.items():
            with self.subTest(name=name):
                result = self.build_for(name).build_command(("frida", "-n", "App Name"))
                self.assertTrue(result.ok)
                self.assertEqual(result.command, (f"/usr/bin/{name}", flag, "frida", "-n", "App Name"))

    def test_windows_powershell_quotes_space_and_apostrophe(self):
        terminal = ExternalTerminal(
            which=lambda name: "C:/PowerShell.exe" if name == "powershell" else None,
            launcher=lambda _command: object(), platform_name="nt",
        )
        result = terminal.build_command(("frida", "-n", "Doctor's App"))
        self.assertEqual(result.command[:3], ("C:/PowerShell.exe", "-NoExit", "-Command"))
        self.assertIn("'Doctor''s App'", result.command[3])

    def test_missing_terminal_is_structured(self):
        result = ExternalTerminal(which=lambda _name: None, platform_name="posix").build_command(("frida",))
        self.assertFalse(result.ok)
        self.assertIn("terminal", result.error.lower())

    def test_launch_uses_injected_launcher_only(self):
        launched = []
        terminal = ExternalTerminal(
            which=lambda name: "/usr/bin/kitty" if name == "kitty" else None,
            launcher=lambda command: launched.append(command), platform_name="posix",
        )
        result = terminal.launch(("frida", "-n", "App Name"))
        self.assertTrue(result.ok)
        self.assertEqual(launched[0][-1], "App Name")


if __name__ == "__main__":
    unittest.main()
