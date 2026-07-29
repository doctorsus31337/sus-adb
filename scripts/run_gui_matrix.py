#!/usr/bin/env python3
"""Run every release GUI smoke in a separate cwd and configuration root."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNERS = (
    "run_gui_smoke.py",
    "run_universal_scroll_smoke.py",
    "run_command_palette_smoke.py",
    "run_command_assistant_smoke.py",
    "run_sessions_center_smoke.py",
    "run_script_studio_smoke.py",
    "run_addons_center_smoke.py",
    "run_addons_update_smoke.py",
    "run_plugin_sdk_v11_smoke.py",
    "run_plugin_workbench_smoke.py",
    "run_plugin_project_wizard_smoke.py",
    "run_device_recovery_smoke.py",
    "run_workflow_recipes_smoke.py",
    "run_guided_help_smoke.py",
    "run_branding_smoke.py",
    "run_pentest_plugin_manager_smoke.py",
)


def main():
    results = []
    for runner in RUNNERS:
        temporary_path = None
        with tempfile.TemporaryDirectory(
            prefix=f"sus-rc4-{Path(runner).stem}-"
        ) as directory:
            temporary_path = Path(directory)
            working_directory = temporary_path / "working directory"
            configuration_directory = temporary_path / "configuration"
            working_directory.mkdir()
            configuration_directory.mkdir()
            environment = os.environ.copy()
            environment["XDG_CONFIG_HOME"] = str(configuration_directory)
            environment["PYTHONPATH"] = str(ROOT)
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / runner)],
                cwd=working_directory,
                env=environment,
                text=True,
                capture_output=True,
                timeout=300,
                check=False,
            )
            if completed.stdout.strip():
                print(completed.stdout.strip(), flush=True)
            if completed.returncode:
                if completed.stderr.strip():
                    print(completed.stderr.strip(), file=sys.stderr)
                raise SystemExit(
                    f"{runner} failed with exit {completed.returncode}"
                )
            results.append((runner, completed.returncode))
        assert temporary_path is not None and not temporary_path.exists()
    print(
        "gui-matrix=PASS "
        f"isolated-runners={len(results)} "
        "separate-cwd=PASS separate-config=PASS cleanup=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
