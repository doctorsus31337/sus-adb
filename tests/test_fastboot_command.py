import unittest

from app.core.fastboot_command import (
    FastbootCommandKind,
    FastbootCommandPolicy,
)


class FastbootCommandPolicyTests(unittest.TestCase):
    def parse(self, *arguments):
        return FastbootCommandPolicy.parse(("fastboot", *arguments))

    def test_exact_read_only_grammar_is_allowed(self):
        expected = {
            ("--version",): FastbootCommandKind.VERSION,
            ("help",): FastbootCommandKind.HELP,
            ("devices",): FastbootCommandKind.DEVICES,
            ("devices", "-l"): FastbootCommandKind.DEVICES_LONG,
            ("-s", "SERIAL", "getvar", "product"): FastbootCommandKind.GETVAR,
            ("--serial", "SERIAL", "getvar", "all"): FastbootCommandKind.GETVAR,
        }
        for arguments, kind in expected.items():
            with self.subTest(arguments=arguments):
                result = self.parse(*arguments)
                self.assertTrue(result.allowed)
                self.assertEqual(result.kind, kind)

    def test_getvar_retains_exact_explicit_fastboot_serial(self):
        result = self.parse("--serial", "FB-123:transport", "getvar", "current-slot")
        self.assertEqual(result.serial, "FB-123:transport")
        self.assertEqual(result.variable, "current-slot")

    def test_missing_empty_duplicate_and_option_serials_are_rejected(self):
        rejected = (
            ("getvar", "product"),
            ("-s", "", "getvar", "product"),
            ("-s", "-SERIAL", "getvar", "product"),
            ("-s", "SERIAL", "--serial", "OTHER", "getvar", "product"),
        )
        for arguments in rejected:
            with self.subTest(arguments=arguments):
                self.assertFalse(self.parse(*arguments).allowed)

    def test_missing_variable_extra_arguments_and_unknown_options_are_rejected(self):
        rejected = (
            ("-s", "SERIAL", "getvar"),
            ("-s", "SERIAL", "getvar", "product", "extra"),
            ("--force", "devices"),
            ("-w",),
            ("--slot", "a", "devices"),
        )
        for arguments in rejected:
            with self.subTest(arguments=arguments):
                self.assertFalse(self.parse(*arguments).allowed)

    def test_destructive_unknown_and_path_like_forms_are_rejected(self):
        rejected = (
            ("flash", "boot", "boot.img"),
            ("flashall",),
            ("erase", "userdata"),
            ("format", "userdata"),
            ("update", "image.zip"),
            ("boot", "boot.img"),
            ("set_active", "a"),
            ("--set-active=a",),
            ("flashing", "unlock"),
            ("flashing", "lock"),
            ("flashing", "unlock_critical"),
            ("flashing", "lock_critical"),
            ("oem", "fixture"),
            ("reboot",),
            ("reboot-bootloader",),
            ("reboot", "recovery"),
            ("reboot", "fastboot"),
            ("create-logical-partition", "fixture", "1"),
            ("delete-logical-partition", "fixture"),
            ("resize-logical-partition", "fixture", "1"),
            ("wipe-super", "super_empty.img"),
            ("snapshot-update", "cancel"),
            ("fetch", "boot", "boot.img"),
            ("stage", "payload.bin"),
            ("get_staged", "payload.bin"),
            ("-s", "../SERIAL", "getvar", "product"),
            ("-s", "SERIAL", "getvar", "../product"),
            ("mystery",),
        )
        for arguments in rejected:
            with self.subTest(arguments=arguments):
                result = self.parse(*arguments)
                self.assertFalse(result.allowed)
                self.assertIn("not supported", result.reason)

    def test_shell_metacharacters_and_control_characters_are_rejected(self):
        for value in ("SERIAL;", "SERIAL&&whoami", "SERIAL\nnext", "$(whoami)"):
            with self.subTest(value=value):
                self.assertFalse(
                    self.parse("-s", value, "getvar", "product").allowed
                )
        self.assertFalse(self.parse("devices", ";", "whoami").allowed)

    def test_serial_and_variable_lengths_are_bounded(self):
        self.assertFalse(
            self.parse("-s", "S" * 129, "getvar", "product").allowed
        )
        self.assertFalse(
            self.parse("-s", "SERIAL", "getvar", "v" * 65).allowed
        )


if __name__ == "__main__":
    unittest.main()
