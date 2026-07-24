import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.device_recovery_service import (
    ADBRecoveryBackend,
    DestinationPreflight,
    DeviceRecoveryService,
    RecoveryCancellation,
    RecoveryItem,
    RecoveryLimits,
    RecoveryPlan,
    RemoteRecoveryEntry,
    StorageScan,
    manifest,
)


class FakeBackend:
    def __init__(self, entries=(), data=None, state="device", resolved="/storage/emulated/0"):
        self.entries = tuple(entries)
        self.data = dict(data or {})
        self.current_state = state
        self.resolved = resolved
        self.pulls = []
        self.fail = set()

    def state(self, serial):
        return self.current_state

    def resolve_path(self, serial, path):
        return self.resolved

    def identity(self, serial):
        return "uid=1023(media_rw) user=0"

    def inventory(self, serial, path, *, depth, limit):
        if path == self.resolved:
            return self.entries[:limit]
        return ()

    def pull(self, serial, source, destination):
        self.pulls.append((serial, source, destination))
        if source in self.fail:
            return SimpleNamespace(ok=False, output="Permission denied")
        Path(destination).write_bytes(self.data[source])
        return SimpleNamespace(ok=True, output="")


def disk_with(free):
    return lambda _path: SimpleNamespace(total=free * 2, used=free, free=free)


class DeviceRecoveryServiceTests(unittest.TestCase):
    def entries(self):
        return (
            RemoteRecoveryEntry("/storage/emulated/0/DCIM", "directory", 0, "1"),
            RemoteRecoveryEntry("/storage/emulated/0/DCIM/a.jpg", "file", 3, "2"),
            RemoteRecoveryEntry("/storage/emulated/0/root.txt", "file", 4, "3"),
        )

    def service(self, backend, serial_ref=None, free=10_000):
        selected = serial_ref or {"value": "SERIAL"}
        return DeviceRecoveryService(
            backend,
            selected_serial_provider=lambda: selected["value"],
            clock=lambda: "2026-07-24T12:00:00+00:00",
            monotonic=lambda: 10.0,
            disk_usage=disk_with(free),
        )

    def test_shared_storage_alias_resolves_and_reports_nonzero_inventory(self):
        service = self.service(FakeBackend(self.entries()))
        scan = service.scan_shared_storage("SERIAL", "/sdcard")
        self.assertTrue(scan.ok)
        self.assertEqual(scan.resolved_path, "/storage/emulated/0")
        self.assertEqual(scan.estimated_bytes, 7)
        self.assertEqual(scan.file_count, 2)
        self.assertEqual(scan.folder_count, 1)
        self.assertEqual(scan.loose_file_count, 1)
        self.assertEqual(len(scan.top_level_entries), 2)
        self.assertIn("user=0", scan.identity)

    def test_unauthorized_offline_and_disconnected_do_not_scan(self):
        for state in ("unauthorized", "offline", "disconnected"):
            backend = FakeBackend(self.entries(), state=state)
            result = self.service(backend).scan_shared_storage("SERIAL")
            self.assertFalse(result.ok)
            self.assertIn(state, result.errors[0])

    def test_private_paths_require_explicit_host_scope_gate(self):
        entry = RemoteRecoveryEntry("/data/local/tmp/selected.txt", "file", 1)
        backend = FakeBackend((entry,), resolved="/data/local/tmp")
        service = self.service(backend)
        blocked = service.scan_shared_storage(
            "SERIAL", "/data/local/tmp", custom_paths=("/data/local/tmp/selected.txt",)
        )
        allowed = service.scan_shared_storage(
            "SERIAL", "/data/local/tmp", custom_paths=("/data/local/tmp/selected.txt",),
            allow_private=True,
        )
        self.assertFalse(blocked.ok)
        self.assertTrue(allowed.ok)

    def test_destination_capacity_and_safety_headroom(self):
        with tempfile.TemporaryDirectory() as directory:
            blocked = self.service(FakeBackend(), free=109).preflight_destination(
                directory, 100, safety_headroom=0.10
            )
            ready = self.service(FakeBackend(), free=110).preflight_destination(
                directory, 100, safety_headroom=0.10
            )
            self.assertFalse(blocked.ok)
            self.assertTrue(ready.ok)
            self.assertEqual(ready.safety_bytes, 10)
            self.assertIn("SUS-Recovery-", ready.recovery_path)

    def test_zero_or_unknown_estimate_requires_bounded_file_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            entry = RemoteRecoveryEntry("/storage/emulated/0/unknown.bin", "file", None)
            scan = StorageScan(
                True, "SERIAL", "/sdcard", "/storage/emulated/0",
                (entry,), (entry,), 0, 1, 1, None,
            )
            service = self.service(FakeBackend((entry,)))
            blocked = service.build_plan(scan, (entry.source,), directory)
            allowed = service.build_plan(
                scan, (entry.source,), directory,
                acknowledge_unknown=True, bounded_selected_files=True,
            )
            self.assertFalse(blocked.ok)
            self.assertTrue(allowed.ok)
            self.assertIsNone(allowed.destination.required_bytes)

    def test_selected_folders_only_are_queued(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(FakeBackend(self.entries()))
            scan = service.scan_shared_storage("SERIAL")
            plan = service.build_plan(
                scan, ("/storage/emulated/0/DCIM",), directory
            )
            self.assertTrue(plan.ok)
            self.assertEqual([entry.source for entry in plan.entries], ["/storage/emulated/0/DCIM/a.jpg"])

    def test_permission_denied_continues_and_reports_partial_success(self):
        entries = self.entries()[1:]
        backend = FakeBackend(
            entries,
            data={
                "/storage/emulated/0/DCIM/a.jpg": b"abc",
                "/storage/emulated/0/root.txt": b"data",
            },
        )
        backend.fail.add("/storage/emulated/0/DCIM/a.jpg")
        with tempfile.TemporaryDirectory() as directory:
            scan = StorageScan(
                True, "SERIAL", "/sdcard", "/storage/emulated/0",
                entries, entries, 0, 2, 1, 7,
            )
            service = self.service(backend)
            plan = service.build_plan(scan, ("/storage/emulated/0",), directory)
            result = service.execute(plan)
            self.assertFalse(result.ok)
            self.assertTrue(result.partial_success)
            self.assertEqual([item.state for item in result.items], ["failed", "recovered"])
            self.assertEqual(result.items[1].sha256, hashlib.sha256(b"data").hexdigest())
            self.assertEqual([call[1] for call in backend.pulls], [entry.source for entry in entries])
            self.assertTrue(Path(result.manifest_path).is_file())

    def test_cancellation_preserves_manifest_and_resume_finishes_same_serial(self):
        entries = self.entries()[1:]
        backend = FakeBackend(
            entries,
            data={
                "/storage/emulated/0/DCIM/a.jpg": b"abc",
                "/storage/emulated/0/root.txt": b"data",
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            scan = StorageScan(
                True, "SERIAL", "/sdcard", "/storage/emulated/0",
                entries, entries, 0, 2, 1, 7,
            )
            service = self.service(backend)
            plan = service.build_plan(scan, ("/storage/emulated/0",), directory)
            token = RecoveryCancellation()

            def progress(value):
                if value.files_completed == 1:
                    token.cancel()

            first = service.execute(plan, cancellation=token, progress=progress)
            self.assertTrue(first.cancelled)
            self.assertEqual(len(first.items), 1)
            resumed = service.resume(plan, first.manifest_path)
            self.assertTrue(resumed.ok)
            self.assertEqual([item.state for item in resumed.items], ["resumed", "recovered"])
            data = json.loads(Path(resumed.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "complete")
            self.assertEqual(data["serial"], "SERIAL")

    def test_serial_change_is_rejected_before_and_during_copy(self):
        entries = self.entries()[1:]
        backend = FakeBackend(entries, data={entry.source: b"x" for entry in entries})
        selected = {"value": "OTHER"}
        with tempfile.TemporaryDirectory() as directory:
            scan = StorageScan(
                True, "SERIAL", "/sdcard", "/storage/emulated/0",
                entries, entries, 0, 2, 1, 7,
            )
            service = self.service(backend, selected)
            plan = service.build_plan(scan, ("/storage/emulated/0",), directory)
            rejected = service.execute(plan)
            self.assertTrue(rejected.interrupted)
            self.assertFalse(Path(plan.destination.recovery_path).exists())
            selected["value"] = "SERIAL"

            def change_after_first(value):
                if value.files_completed == 1:
                    selected["value"] = "OTHER"

            interrupted = service.execute(plan, progress=change_after_first)
            self.assertTrue(interrupted.interrupted)
            self.assertEqual(len(interrupted.items), 1)

    def test_duplicate_policies_and_priority_order(self):
        critical = RemoteRecoveryEntry("/storage/emulated/0/DCIM/a.jpg", "file", 1)
        ordinary = RemoteRecoveryEntry("/storage/emulated/0/Download/b.txt", "file", 1)
        backend = FakeBackend((ordinary, critical), data={critical.source: b"a", ordinary.source: b"b"})
        with tempfile.TemporaryDirectory() as directory:
            scan = StorageScan(
                True, "SERIAL", "/sdcard", "/storage/emulated/0",
                (ordinary, critical), (), 0, 2, 0, 2,
            )
            service = self.service(backend)
            plan = service.build_plan(
                scan, ("/storage/emulated/0",), directory,
                duplicate_policy="rename", priorities={"/storage/emulated/0/DCIM": 1},
            )
            result = service.execute(plan)
            self.assertTrue(result.ok)
            self.assertEqual([call[1] for call in backend.pulls], [critical.source, ordinary.source])
            self.assertFalse(
                service.build_plan(
                    scan, ("/storage/emulated/0",), directory,
                    duplicate_policy="replace",
                ).ok
            )
            confirmed = service.build_plan(
                scan, ("/storage/emulated/0",), directory,
                duplicate_policy="replace", replace_confirmed=True,
            )
            self.assertTrue(confirmed.ok)

    def test_resume_rejects_manifest_from_another_serial(self):
        entry = RemoteRecoveryEntry("/storage/emulated/0/a.txt", "file", 1)
        backend = FakeBackend((entry,), data={entry.source: b"a"})
        with tempfile.TemporaryDirectory() as directory:
            scan = StorageScan(
                True, "SERIAL", "/sdcard", "/storage/emulated/0",
                (entry,), (entry,), 0, 1, 1, 1,
            )
            service = self.service(backend)
            plan = service.build_plan(scan, (entry.source,), directory)
            manifest_file = Path(directory) / "other" / "recovery-manifest.json"
            manifest_file.parent.mkdir()
            manifest_file.write_text(
                json.dumps(
                    {
                        "serial": "OTHER",
                        "destination": str(manifest_file.parent),
                        "items": [],
                    }
                ),
                encoding="utf-8",
            )
            result = service.resume(plan, str(manifest_file))
            self.assertFalse(result.ok)
            self.assertTrue(result.interrupted)
            self.assertEqual(backend.pulls, [])

    def test_manifest_is_deterministic_and_no_delete_surface_exists(self):
        first = RecoveryItem("/b", "/dest/b", 1, "1", "2", "a" * 64, "recovered")
        second = RecoveryItem("/a", "/dest/a", 1, "1", "2", "b" * 64, "recovered")
        self.assertEqual(manifest((first, second)), manifest((second, first)))
        source = Path(__file__).parents[1] / "app/core/device_recovery_service.py"
        text = source.read_text(encoding="utf-8")
        self.assertNotIn('"delete"', text)
        self.assertNotIn("shell=True", text)

    def test_adb_inventory_parser_handles_spaces_and_variant_lines(self):
        parsed = ADBRecoveryBackend.parse_inventory(
            "d\t0\t1\t/storage/emulated/0/My Folder\n"
            "f\t42\t2\t/storage/emulated/0/My Folder/a file.txt\n"
            "unexpected toolbox output\n",
            10,
        )
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[1].size, 42)
        self.assertTrue(parsed[1].source.endswith("a file.txt"))

    def test_adb_fallback_stat_and_pull_keep_explicit_serial_and_safe_argv(self):
        class FakeADB:
            def __init__(self):
                self.calls = []

            def run(self, *args, serial=None, timeout=0):
                self.calls.append((args, serial))
                if args[:3] == ("shell", "sh", "-c"):
                    return SimpleNamespace(ok=False, stdout="", output="unsupported")
                if args[:2] == ("shell", "find"):
                    return SimpleNamespace(
                        ok=True, stdout="/storage/emulated/0/a file.txt", output=""
                    )
                if args[:2] == ("shell", "stat"):
                    return SimpleNamespace(
                        ok=True, stdout="regular file\t12\t123", output=""
                    )
                if args[0] == "pull":
                    return SimpleNamespace(ok=True, stdout="", output="")
                raise AssertionError(args)

        adb = FakeADB()
        backend = ADBRecoveryBackend(adb)
        entries = backend.inventory(
            "SERIAL", "/storage/emulated/0", depth=2, limit=5
        )
        backend.pull("SERIAL", entries[0].source, "/host path/a file.txt")
        self.assertEqual(entries[0].size, 12)
        self.assertTrue(all(serial == "SERIAL" for _args, serial in adb.calls))
        self.assertIn(
            ("pull", "/storage/emulated/0/a file.txt", "/host path/a file.txt"),
            [args for args, _serial in adb.calls],
        )


if __name__ == "__main__":
    unittest.main()
