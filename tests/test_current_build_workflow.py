import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class CurrentBuildWorkflowTests(unittest.TestCase):
    def test_manual_chosen_ref_workflow_is_read_only_and_never_publishes(self):
        workflow = (ROOT / ".github/workflows/package.yml").read_text()
        self.assertIn("name: Package Current Testing Build", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("ref: ${{ inputs.ref }}", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("short_commit", workflow)
        self.assertIn("safe_ref", workflow)
        self.assertIn("SUS_ADB_BUILD_CHANNEL: rc", workflow)
        self.assertIn("default: release/1.0.0-rc.4", workflow)
        for forbidden in (
            "actions/create-release", "softprops/action-gh-release",
            "gh release", "git tag", "contents: write",
        ):
            self.assertNotIn(forbidden, workflow)

    def test_platform_builds_emit_identity_report_manifest_and_legacy_launcher(self):
        linux = (ROOT / "packaging/linux/build_linux.sh").read_text()
        windows = (ROOT / "packaging/windows/build_windows.ps1").read_text()
        for source in (linux, windows):
            self.assertIn("generate_build_info.py", source)
            self.assertIn("generate_checksums.py", source)
            self.assertIn("verification-report.json", source)
            self.assertIn("build-info.json", source)
            self.assertIn("sus-adb", source)
        self.assertIn(".tar.gz", linux)
        self.assertIn("Compress-Archive", windows)
        spec = (ROOT / "packaging/pyinstaller/sus_adb.spec").read_text()
        self.assertIn("name='sus-companion'", spec)
        self.assertIn("build-info.json", spec)
        self.assertIn("assets/branding/runtime", spec)
        self.assertIn("sus-companion.ico", spec)
        self.assertIn("Icon=sus-companion", (ROOT / "packaging/linux/sus-adb.desktop").read_text())
        self.assertIn("sus-companion.png", linux)

    def test_readme_and_publication_plan_identify_rc4(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Accepted RC source branch: `release/1.0.0-rc.4`", readme)
        self.assertIn("Current RC tag: `v1.0.0-rc.4`", readme)
        self.assertIn("python main.py", readme)
        plan = (ROOT / "release/RC4_PUBLICATION_PLAN.md").read_text()
        self.assertIn("explicitly", plan)
        self.assertIn("release/1.0.0-rc.4", plan)

    def test_windows_regressions_are_explicit_in_ci(self):
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        self.assertIn("test_customtkinter_compat.py", workflow)
        self.assertIn("test_addon_ui.py", workflow)
        self.assertIn("test_external_terminal.py", workflow)


if __name__ == "__main__":
    unittest.main()
