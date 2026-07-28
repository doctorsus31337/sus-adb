import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from app.plugins.plugin_project import (
    PROJECT_FILES,
    PluginProjectCapabilityPlan,
    PluginProjectContributionSpec,
    PluginProjectDeveloperDetails,
    PluginProjectGenerator,
    PluginProjectIdentity,
    PluginProjectSpec,
    portable_folder_name,
    suggest_contribution_id,
    suggest_plugin_id,
)


def project_spec(**identity_overrides):
    values = {
        "display_name": "Fixture Addon",
        "plugin_id": "example.fixture-addon",
        "author": "Example Author",
        "description": "An inert synthetic fixture.",
        "folder_name": "fixture-addon",
        **identity_overrides,
    }
    identity = PluginProjectIdentity(
        **values,
    )
    contribution = PluginProjectContributionSpec(
        "example.fixture-addon.main", "Fixture Addon"
    )
    return PluginProjectSpec(
        identity,
        contribution,
        developer=PluginProjectDeveloperDetails(
            intended_purpose="Explain a bounded local workflow.",
            operator_workflow="Enter a label and click explicitly.",
        ),
    )


class PluginProjectGeneratorTests(unittest.TestCase):
    def test_models_are_immutable_and_suggestions_are_deterministic(self):
        identity = project_spec().identity
        with self.assertRaises(FrozenInstanceError):
            identity.plugin_id = "changed"
        self.assertEqual(
            suggest_plugin_id("Example Author", "Fixture Addon"),
            "example-author.fixture-addon",
        )
        self.assertEqual(
            suggest_contribution_id("example.fixture"), "example.fixture.main"
        )

    def test_plugin_id_suggestion_removes_only_exact_publisher_token_prefix(self):
        fixtures = (
            ("DoctorSUS", "DoctorSUS wiz", "doctorsus.wiz"),
            (
                "DoctorSUS",
                "DoctorSUS Wizard Live Test",
                "doctorsus.wizard-live-test",
            ),
            ("doctor", "doctors helper", "doctor.doctors-helper"),
            ("DoctorSUS", "DoctorSUS", "doctorsus.plugin"),
        )
        for author, project, expected in fixtures:
            with self.subTest(author=author, project=project):
                self.assertEqual(
                    suggest_plugin_id(author, project), expected
                )
                self.assertEqual(
                    suggest_plugin_id(author, project), expected
                )

    def test_identity_semver_reserved_and_portable_names(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            project_spec(plugin_id="susadb.skeleton-module")
        with self.assertRaises(ValueError):
            project_spec(plugin_id="Bad ID")
        with self.assertRaises(ValueError):
            project_spec(version="1")
        for value in ("CON", "NUL.txt", "bad.", " bad", "bad/name", "bad:name"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                portable_folder_name(value)
        self.assertEqual(portable_folder_name("Project With Spaces"), value := "Project With Spaces")
        self.assertEqual(value, "Project With Spaces")

    def test_contribution_geometry_capabilities_and_ownership(self):
        with self.assertRaises(ValueError):
            PluginProjectContributionSpec(
                "example.main", "Example", contribution_type="future"
            )
        with self.assertRaises(ValueError):
            PluginProjectContributionSpec(
                "example.main", "Example", minimum_width=1200, default_width=900
            )
        with self.assertRaises(ValueError):
            PluginProjectCapabilityPlan(("unknown",))
        with self.assertRaisesRegex(ValueError, "acknowledgment"):
            PluginProjectCapabilityPlan(("access-network",))
        plan = PluginProjectCapabilityPlan(
            ("read-selected-device", "read-selected-device")
        )
        self.assertEqual(plan.requested, ("read-selected-device",))
        with self.assertRaises(ValueError):
            PluginProjectSpec(
                project_spec().identity,
                PluginProjectContributionSpec("other.main", "Other"),
            )

    def test_generation_is_byte_identical_complete_and_private_path_free(self):
        generator = PluginProjectGenerator()
        first = generator.plan(project_spec())
        second = generator.plan(project_spec())
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(
            tuple(value.path for value in first.files), tuple(sorted(PROJECT_FILES))
        )
        content = b"".join(value.content for value in first.files)
        developer_home_prefix = b"/" + b"home/"
        self.assertNotIn(developer_home_prefix, content)
        self.assertNotIn(b"C:\\Users\\", content)
        self.assertNotIn(b"timestamp", content.lower())
        self.assertNotIn(b".success", first.file("plugin.py").content)
        self.assertNotIn(b"subprocess", first.file("plugin.py").content)
        self.assertNotIn(b"customtkinter", first.file("plugin.py").content)

    def test_manifest_registration_brief_and_static_validation(self):
        generator = PluginProjectGenerator()
        plan = generator.plan(project_spec())
        manifest = json.loads(plan.file("manifest.json").text)
        self.assertEqual(manifest["plugin_api_version"], "1.1")
        self.assertFalse(manifest["enabled"])
        self.assertEqual(manifest["trust_state"], "untrusted")
        self.assertEqual(manifest["requested_capabilities"], [])
        contribution_id = manifest["contributed_components"][0]["contribution_id"]
        self.assertEqual(contribution_id, "example.fixture-addon.main")
        self.assertIn(repr(contribution_id), plan.file("plugin.py").text)
        brief = plan.file("DEVELOPER_BRIEF.md").text
        self.assertIn("example.fixture-addon", brief)
        self.assertIn("example.fixture-addon.main", brief)
        self.assertIn("Private `app.core` and `app.gui` imports are", brief)
        validation = generator.validate(plan)
        self.assertTrue(validation.ok, validation.errors)
        self.assertTrue(validation.inspection.ok)
        self.assertFalse(any(
            finding.severity.value == "error"
            for finding in validation.workbench.findings
        ))

    def test_reserved_catalog_identity_is_rejected_without_hardcoded_list(self):
        identity = PluginProjectIdentity(
            "Official Fixture", "example.official", author="Author",
            description="Fixture", folder_name="official-fixture",
        )
        spec = PluginProjectSpec(
            identity,
            PluginProjectContributionSpec(
                "example.official.main", "Official Fixture"
            ),
        )
        generator = PluginProjectGenerator({"example.official": False})
        with self.assertRaisesRegex(ValueError, "reserved"):
            generator.plan(spec)

    def test_atomic_folder_write_requires_overwrite_and_supports_spaces(self):
        generator = PluginProjectGenerator()
        plan = generator.plan(project_spec())
        with tempfile.TemporaryDirectory(prefix="project parent ") as value:
            parent = Path(value)
            destination = parent / plan.spec.identity.folder_name
            first = generator.write(plan, destination)
            self.assertTrue(first.ok, first.error)
            self.assertEqual(
                tuple(
                    path.relative_to(destination).as_posix()
                    for path in sorted(destination.rglob("*"))
                    if path.is_file()
                ),
                tuple(sorted(PROJECT_FILES)),
            )
            marker = destination / "existing.txt"
            marker.write_text("preserve", encoding="utf-8")
            declined = generator.write(plan, destination)
            self.assertFalse(declined.ok)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            replaced = generator.write(plan, destination, overwrite=True)
            self.assertTrue(replaced.ok, replaced.error)
            self.assertFalse(marker.exists())

    def test_failed_folder_write_preserves_existing_and_removes_staging(self):
        class FailingGenerator(PluginProjectGenerator):
            def __init__(self):
                super().__init__()
                self.materializations = 0

            def _materialize(self, plan, root):
                self.materializations += 1
                if self.materializations == 2:
                    raise OSError("synthetic write failure")
                return super()._materialize(plan, root)

        generator = FailingGenerator()
        plan = generator.plan(project_spec())
        with tempfile.TemporaryDirectory() as value:
            destination = Path(value) / plan.spec.identity.folder_name
            destination.mkdir()
            marker = destination / "existing.txt"
            marker.write_text("preserved", encoding="utf-8")
            result = generator.write(plan, destination, overwrite=True)
            self.assertFalse(result.ok)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserved")
            self.assertEqual(
                tuple(path.name for path in Path(value).iterdir()),
                (plan.spec.identity.folder_name,),
            )


if __name__ == "__main__":
    unittest.main()
