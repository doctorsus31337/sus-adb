import unittest

from app.core.command_result import CommandResult
from app.core.frida_target import TargetType
from app.core.target_discovery import TargetDiscovery, filter_targets


class FakeFrida:
    def __init__(self, applications="", processes="", failure=None):
        self.applications = applications
        self.processes = processes
        self.failure = failure
        self.calls = []

    def list_applications(self, serial):
        self.calls.append(("applications", serial))
        if self.failure:
            return CommandResult.from_command(("frida-ps",), 1, error=self.failure)
        return CommandResult.from_command(("frida-ps",), 0, stdout=self.applications)

    def list_processes(self, serial):
        self.calls.append(("processes", serial))
        if self.failure:
            return CommandResult.from_command(("frida-ps",), 1, error=self.failure)
        return CommandResult.from_command(("frida-ps",), 0, stdout=self.processes)


APPLICATIONS = """ PID  Name                 Identifier
----  -------------------  -----------------------
 123  Example App          com.example.app
   -  Another App          org.example.another
 123  Example App          com.example.app
 456                       net.blank.name
bad malformed row
"""

PROCESSES = """ PID  Name
----  ----------------
 77   System UI Process
 12   alpha
 77   System UI Process
 -    malformed
"""


class TargetDiscoveryTests(unittest.TestCase):
    def test_parse_applications_identifiers_pids_blank_names_and_duplicates(self):
        targets = TargetDiscovery.parse_applications(APPLICATIONS)
        self.assertEqual(len(targets), 3)
        example = next(target for target in targets if target.identifier == "com.example.app")
        self.assertEqual(example.pid, 123)
        self.assertTrue(example.running)
        blank = next(target for target in targets if target.identifier == "net.blank.name")
        self.assertEqual(blank.name, "")
        self.assertEqual(blank.pid, 456)

    def test_running_application_replaces_installed_duplicate(self):
        output = "- Example com.example.app\n321 Example com.example.app"
        targets = TargetDiscovery.parse_applications(output)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].pid, 321)

    def test_parse_process_names_with_spaces_and_stable_sorting(self):
        targets = TargetDiscovery.parse_processes(PROCESSES)
        self.assertEqual([target.name for target in targets], ["alpha", "System UI Process"])
        self.assertTrue(all(target.target_type is TargetType.PROCESS for target in targets))

    def test_discovery_targets_only_explicit_serial(self):
        frida = FakeFrida(APPLICATIONS, PROCESSES)
        result = TargetDiscovery(frida).discover_combined("SERIAL-1")
        self.assertTrue(result.ok)
        self.assertEqual(frida.calls, [("applications", "SERIAL-1"), ("processes", "SERIAL-1")])

    def test_no_serial_and_command_failure_are_structured(self):
        frida = FakeFrida(failure="unreachable")
        self.assertFalse(TargetDiscovery(frida).discover_combined(None).ok)
        result = TargetDiscovery(frida).discover_applications("SERIAL")
        self.assertFalse(result.ok)
        self.assertIn("unreachable", result.errors[0])

    def test_filtering_is_local_and_type_aware(self):
        frida = FakeFrida(APPLICATIONS, PROCESSES)
        discovery = TargetDiscovery(frida)
        targets = discovery.discover_combined("SERIAL").targets
        call_count = len(frida.calls)
        filtered = filter_targets(targets, "example", "applications")
        self.assertEqual({target.identifier for target in filtered}, {"com.example.app", "org.example.another"})
        self.assertEqual(len(frida.calls), call_count)


if __name__ == "__main__":
    unittest.main()
