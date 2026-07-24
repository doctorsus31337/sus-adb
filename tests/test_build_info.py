import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_build_info",
    ROOT / "packaging/common/generate_build_info.py",
)
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class BuildInfoTests(unittest.TestCase):
    def test_explicit_ci_identity_is_deterministic_and_does_not_probe_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            calls = []
            info = BUILD.collect_build_info(
                root,
                environ={
                    "SUS_ADB_REVISION": "a" * 40,
                    "SUS_ADB_REF": "feature/selected ref",
                    "SUS_ADB_BUILD_TIMESTAMP": "2026-07-24T12:00:00Z",
                    "SUS_ADB_BUILD_CHANNEL": "current-testing",
                },
                runner=lambda *args, **kwargs: calls.append((args, kwargs)),
            )
            self.assertFalse(calls)
            self.assertEqual(info["version"], "1.2.3")
            self.assertEqual(info["short_commit"], "a" * 12)
            self.assertEqual(info["ref"], "feature/selected ref")
            self.assertEqual(info["channel"], "current-testing")

    def test_local_git_fallback_timestamp_and_json_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("1.0.0-rc.1\n", encoding="utf-8")
            values = {
                ("git", "rev-parse", "HEAD"): "b" * 40,
                ("git", "branch", "--show-current"): "feature/local",
            }

            def runner(argv, **_kwargs):
                return SimpleNamespace(
                    returncode=0, stdout=values.get(tuple(argv), "") + "\n"
                )

            info = BUILD.collect_build_info(
                root,
                environ={},
                clock=lambda: datetime(
                    2026, 7, 24, 12, 0, tzinfo=timezone.utc
                ),
                runner=runner,
            )
            output = BUILD.write_build_info(root / "out/build-info.json", info)
            self.assertEqual(json.loads(output.read_text()), info)
            self.assertEqual(info["ref"], "feature/local")
            self.assertEqual(info["timestamp"], "2026-07-24T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
