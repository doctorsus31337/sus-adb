import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.core.assessment_scope import AssessmentScope
from app.core.pentest_session import PentestSession
from scripts.run_gui_smoke import isolated_smoke_environment


class GuiSmokeIsolationTests(unittest.TestCase):
    def _authorized_workspace(self, caller):
        case = Path(caller) / "workspaces" / "authorized-fixture"
        scope = AssessmentScope(
            "authorized-fixture",
            "Authorized Fixture",
            authorization_confirmed=True,
            device_serial="fixture-serial",
            package_identifier="org.example.fixture",
            allowed_actions=("recon",),
            start_date=date.today().isoformat(),
        )
        session = PentestSession.draft(scope, case)
        self.assertTrue(session.save_case().ok)
        return {
            path: path.read_bytes()
            for path in (case / "case.json", case / "scope.json")
        }

    def _restore_process_state(self, cwd, had_xdg, xdg):
        os.chdir(cwd)
        if had_xdg:
            os.environ["XDG_CONFIG_HOME"] = xdg
        else:
            os.environ.pop("XDG_CONFIG_HOME", None)

    def test_caller_workspace_is_ignored_and_process_state_is_restored(self):
        original_cwd = Path.cwd()
        had_xdg = "XDG_CONFIG_HOME" in os.environ
        original_xdg = os.environ.get("XDG_CONFIG_HOME")
        try:
            with tempfile.TemporaryDirectory() as root:
                root = Path(root)
                caller = root / "caller with authorized workspace"
                caller.mkdir()
                original_files = self._authorized_workspace(caller)
                smoke_root = root / "smoke resources"
                smoke_root.mkdir()
                os.chdir(caller)
                os.environ["XDG_CONFIG_HOME"] = str(root / "caller configuration")

                with isolated_smoke_environment(smoke_root) as (
                    working_directory,
                    configuration_directory,
                ):
                    self.assertEqual(Path.cwd(), working_directory)
                    self.assertEqual(
                        os.environ["XDG_CONFIG_HOME"],
                        str(configuration_directory),
                    )
                    self.assertEqual(
                        PentestSession.load_last("workspaces").session,
                        None,
                    )
                    self.assertFalse((working_directory / "workspaces").exists())

                self.assertEqual(Path.cwd(), caller)
                self.assertEqual(
                    os.environ["XDG_CONFIG_HOME"],
                    str(root / "caller configuration"),
                )
                self.assertEqual(
                    {path: path.read_bytes() for path in original_files},
                    original_files,
                )
        finally:
            self._restore_process_state(
                original_cwd, had_xdg, original_xdg
            )

    def test_cwd_and_unset_environment_are_restored_after_exception(self):
        original_cwd = Path.cwd()
        had_xdg = "XDG_CONFIG_HOME" in os.environ
        original_xdg = os.environ.get("XDG_CONFIG_HOME")
        temporary_path = None
        try:
            with tempfile.TemporaryDirectory() as root:
                temporary_path = Path(root)
                caller = temporary_path / "empty caller"
                caller.mkdir()
                os.chdir(caller)
                os.environ.pop("XDG_CONFIG_HOME", None)

                with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                    with isolated_smoke_environment(
                        temporary_path / "smoke resources"
                    ) as (working_directory, configuration_directory):
                        self.assertEqual(Path.cwd(), working_directory)
                        self.assertEqual(
                            os.environ["XDG_CONFIG_HOME"],
                            str(configuration_directory),
                        )
                        raise RuntimeError("fixture failure")

                self.assertEqual(Path.cwd(), caller)
                self.assertNotIn("XDG_CONFIG_HOME", os.environ)
        finally:
            self._restore_process_state(
                original_cwd, had_xdg, original_xdg
            )
        self.assertFalse(temporary_path.exists())


if __name__ == "__main__":
    unittest.main()
