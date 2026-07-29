import os
import tempfile
import unittest
from pathlib import Path

from app.core.config_manager import ConfigManager
from scripts.run_command_palette_smoke import (
    isolated_palette_environment,
    pump_until,
)


class FakeEventApp:
    def __init__(self, ready_after=1):
        self.ready_after = ready_after
        self.updates = 0

    def update(self):
        self.updates += 1

    def update_idletasks(self):
        self.updates += 1


class CommandPaletteSmokeIsolationTests(unittest.TestCase):
    def setUp(self):
        self.original_cwd = Path.cwd()
        self.had_xdg = "XDG_CONFIG_HOME" in os.environ
        self.original_xdg = os.environ.get("XDG_CONFIG_HOME")

    def tearDown(self):
        os.chdir(self.original_cwd)
        if self.had_xdg:
            os.environ["XDG_CONFIG_HOME"] = self.original_xdg
        else:
            os.environ.pop("XDG_CONFIG_HOME", None)

    @staticmethod
    def _caller_config(root, mode, unrelated=False):
        xdg_root = Path(root) / "caller config"
        directory = xdg_root / "sus-adb"
        manager = ConfigManager(directory)
        data = manager.load().data
        data["interface"]["mode"] = mode
        if unrelated:
            data.setdefault("navigation", {})[
                "last_principal_workspace"
            ] = "Pentest"
            data.setdefault("addon_windows", {})[
                "fixture"
            ] = "900x650+0+0"
        assert manager.save(data).ok
        return xdg_root, manager.path.read_bytes()

    def _assert_isolated_from_caller(self, mode, unrelated=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            caller = root / "caller cwd"
            caller.mkdir()
            caller_xdg, original = self._caller_config(
                root, mode, unrelated
            )
            smoke_root = root / "palette smoke"
            smoke_root.mkdir()
            os.chdir(caller)
            os.environ["XDG_CONFIG_HOME"] = str(caller_xdg)

            with isolated_palette_environment(smoke_root) as (
                working_directory,
                configuration_directory,
            ):
                self.assertEqual(Path.cwd(), working_directory)
                self.assertEqual(
                    os.environ["XDG_CONFIG_HOME"],
                    str(configuration_directory),
                )
                isolated = ConfigManager().load().data
                self.assertEqual(isolated["interface"]["mode"], "guided")
                isolated["interface"]["mode"] = "advanced"
                self.assertTrue(ConfigManager().save(isolated).ok)

            self.assertEqual(Path.cwd(), caller)
            self.assertEqual(
                os.environ["XDG_CONFIG_HOME"], str(caller_xdg)
            )
            self.assertEqual(
                caller_xdg.joinpath("sus-adb/config.json").read_bytes(),
                original,
            )

    def test_caller_guided_state_is_ignored(self):
        self._assert_isolated_from_caller("guided")

    def test_caller_advanced_state_is_ignored(self):
        self._assert_isolated_from_caller("advanced")

    def test_unrelated_prior_gui_state_is_ignored(self):
        self._assert_isolated_from_caller("guided", unrelated=True)

    def test_success_restores_cwd_environment_and_removes_temporary_root(self):
        temporary_path = None
        with tempfile.TemporaryDirectory() as caller_directory:
            caller = Path(caller_directory)
            os.chdir(caller)
            os.environ.pop("XDG_CONFIG_HOME", None)
            with tempfile.TemporaryDirectory() as directory:
                temporary_path = Path(directory)
                smoke = temporary_path / "smoke"
                smoke.mkdir()
                with isolated_palette_environment(smoke):
                    self.assertNotEqual(Path.cwd(), caller)
                    self.assertIn("XDG_CONFIG_HOME", os.environ)
            self.assertEqual(Path.cwd(), caller)
            self.assertNotIn("XDG_CONFIG_HOME", os.environ)
            self.assertFalse(temporary_path.exists())
            os.chdir(self.original_cwd)

    def test_failure_restores_cwd_environment_and_removes_temporary_root(self):
        temporary_path = None
        with tempfile.TemporaryDirectory() as caller_directory:
            caller = Path(caller_directory)
            original_config = caller / "original config"
            os.chdir(caller)
            os.environ["XDG_CONFIG_HOME"] = str(original_config)
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                with tempfile.TemporaryDirectory() as directory:
                    temporary_path = Path(directory)
                    smoke = temporary_path / "smoke"
                    smoke.mkdir()
                    with isolated_palette_environment(smoke):
                        raise RuntimeError("fixture failure")
            self.assertEqual(Path.cwd(), caller)
            self.assertEqual(
                os.environ["XDG_CONFIG_HOME"], str(original_config)
            )
            self.assertFalse(temporary_path.exists())
            os.chdir(self.original_cwd)

    def test_bounded_event_pump_waits_for_actual_condition(self):
        app = FakeEventApp(ready_after=4)
        self.assertTrue(
            pump_until(app, lambda: app.updates >= app.ready_after, timeout=0.2)
        )
        self.assertGreaterEqual(app.updates, 4)

    def test_smoke_keeps_exact_advanced_and_product_mode_contracts(self):
        source = (
            Path(__file__).parents[1]
            / "scripts/run_command_palette_smoke.py"
        ).read_text(encoding="utf-8")
        self.assertIn('app.set_interface_mode("guided")', source)
        self.assertIn('app.set_interface_mode("advanced")', source)
        self.assertIn(
            'palette.mode_label.cget("text") == "Advanced mode"', source
        )
        self.assertIn(
            'published.interface_mode == "advanced"', source
        )
        self.assertIn(
            'app.host_state.subscription_count("command-palette") == 0',
            source,
        )
        self.assertNotIn('in {"guided", "advanced"}', source)
        self.assertNotIn("after(30", source)


if __name__ == "__main__":
    unittest.main()
