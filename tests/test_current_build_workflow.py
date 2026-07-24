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
        self.assertIn("current-testing", workflow)
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
        spec = (ROOT / "packaging/pyinstaller/sus_adb.spec").read_text()
        self.assertIn("name='sus-companion'", spec)
        self.assertIn("build-info.json", spec)

    def test_readme_identifies_tested_and_stable_branches_and_rc2_is_deferred(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn(
            "Latest tested development branch: "
            "`feature/operator-experience-reliability`",
            readme,
        )
        self.assertIn("Stable RC branch: `release/1.0.0-rc.1`", readme)
        self.assertIn("python main.py", readme)
        plan = (ROOT / "release/RC2_PUBLICATION_PLAN.md").read_text()
        self.assertIn("does not authorize or create a branch, tag", plan)
        self.assertIn("release/1.0.0-rc.2", plan)

    def test_windows_regressions_are_explicit_in_ci(self):
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        self.assertIn("test_customtkinter_compat.py", workflow)
        self.assertIn("test_addon_ui.py", workflow)
        self.assertIn("test_external_terminal.py", workflow)


if __name__ == "__main__":
    unittest.main()
