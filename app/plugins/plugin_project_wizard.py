"""GUI-neutral draft and output controller for Plugin Project Wizard v1."""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.plugins.plugin_capabilities import CAPABILITIES, HIGH_IMPACT
from app.plugins.plugin_project import (
    PluginProjectCapabilityPlan,
    PluginProjectContributionSpec,
    PluginProjectDeveloperDetails,
    PluginProjectGenerator,
    PluginProjectIdentity,
    PluginProjectSpec,
    suggest_contribution_id,
    suggest_plugin_id,
)
from app.plugins.plugin_workbench import PluginWorkbenchAnalyzer, PluginWorkbenchSource
from app.plugins.plugin_workbench_output import (
    PluginWorkbenchPackageBuilder,
    WorkbenchWriteResult,
    atomic_write_report,
)


def capability_rows():
    """Project canonical capability values into bounded explanatory rows."""
    from app.plugins.plugin_workbench import PublicSDKIndex

    method_by_capability = {
        capability: method
        for method, capability in PublicSDKIndex.current().method_capabilities.items()
    }
    values = []
    for capability in CAPABILITIES:
        high = capability in HIGH_IMPACT
        method = method_by_capability.get(capability, "")
        values.append({
            "name": capability,
            "purpose": capability.replace("-", " ").capitalize() + ".",
            "impact": "High impact" if high else "Standard",
            "state_changing": high or "modify" in capability or "state-changing" in capability,
            "approval": (
                "Requires explicit high-impact acknowledgment and exact-digest approval."
                if high else "Requires exact-digest capability approval."
            ),
            "facade": (
                f"PluginAPI.{method}" if method
                else "No direct v1.1 façade; declaration alone adds no implementation."
            ),
        })
    return tuple(values)


@dataclass(slots=True)
class PluginProjectDraft:
    project_name: str = ""
    plugin_id: str = ""
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    license: str = "MIT"
    platforms: tuple[str, ...] = ("linux", "windows")
    folder_name: str = ""
    contribution_title: str = ""
    contribution_id: str = ""
    contribution_locked: bool = False
    contribution_type: str = "pentest-panel"
    ui_mode: str = "window"
    singleton: bool = True
    default_width: int = 1080
    default_height: int = 720
    minimum_width: int = 820
    minimum_height: int = 560
    icon: str = "⚙"
    capabilities: tuple[str, ...] = ()
    capability_justifications: dict[str, str] = field(default_factory=dict)
    high_impact_acknowledged: bool = False
    intended_purpose: str = ""
    operator_workflow: str = ""
    planned_inputs: str = ""
    expected_output: str = ""
    cancellation_needs: str = ""
    navigation_destination: str = "contextual-help"
    implementation_notes: str = ""

    @property
    def meaningful(self):
        return any((
            self.project_name.strip(), self.plugin_id.strip(), self.author.strip(),
            self.description.strip(), self.folder_name.strip(),
            self.contribution_title.strip(), self.contribution_id.strip(),
            self.capabilities, self.intended_purpose.strip(),
            self.operator_workflow.strip(), self.implementation_notes.strip(),
        ))


class PluginProjectWizardController:
    """Owns one runtime-only draft; construction performs no filesystem work."""

    def __init__(self, generator_factory=None):
        self.generator_factory = generator_factory or PluginProjectGenerator
        self.preview_generator = PluginProjectGenerator()
        self.draft = PluginProjectDraft()
        self.review_plan = None
        self.validation = None
        self.generated_folder = ""
        self.generated_zip = ""

    def reset(self):
        self.draft = PluginProjectDraft()
        self.review_plan = None
        self.validation = None
        self.generated_folder = ""
        self.generated_zip = ""

    def apply_plugin_id_suggestion(self):
        value = suggest_plugin_id(self.draft.author, self.draft.project_name)
        self.set_plugin_id(value)
        return value

    def apply_folder_suggestion(self):
        value = self.draft.plugin_id.replace(".", "-") or "plugin-project"
        self.draft.folder_name = value
        self._invalidate()
        return value

    def set_plugin_id(self, value):
        old = self.draft.plugin_id
        previous_suggestion = suggest_contribution_id(old) if old else ""
        self.draft.plugin_id = str(value)
        if (
            not self.draft.contribution_locked
            and (
                not self.draft.contribution_id
                or self.draft.contribution_id == previous_suggestion
            )
        ):
            self.draft.contribution_id = suggest_contribution_id(value) if value else ""
        self._invalidate()

    def set_contribution_id(self, value, *, manual=True):
        self.draft.contribution_id = str(value)
        if manual:
            self.draft.contribution_locked = True
        self._invalidate()

    def clear_capabilities(self):
        self.draft.capabilities = ()
        self.draft.capability_justifications.clear()
        self.draft.high_impact_acknowledged = False
        self._invalidate()

    def set_capabilities(self, values):
        self.draft.capabilities = tuple(sorted(set(str(value) for value in values)))
        self._invalidate()

    def _invalidate(self):
        self.review_plan = None
        self.validation = None

    def spec(self):
        draft = self.draft
        identity = PluginProjectIdentity(
            draft.project_name,
            draft.plugin_id,
            draft.version,
            draft.author,
            draft.description,
            draft.license,
            draft.platforms,
            "1.1",
            draft.folder_name,
        )
        contribution = PluginProjectContributionSpec(
            draft.contribution_id,
            draft.contribution_title or draft.project_name,
            draft.contribution_type,
            draft.ui_mode,
            draft.singleton,
            int(draft.default_width),
            int(draft.default_height),
            int(draft.minimum_width),
            int(draft.minimum_height),
            draft.icon,
        )
        capabilities = PluginProjectCapabilityPlan(
            draft.capabilities,
            draft.capability_justifications,
            draft.high_impact_acknowledged,
        )
        developer = PluginProjectDeveloperDetails(
            draft.intended_purpose,
            draft.operator_workflow,
            draft.planned_inputs,
            draft.expected_output,
            draft.cancellation_needs,
            draft.navigation_destination,
            draft.implementation_notes,
        )
        return PluginProjectSpec(identity, contribution, capabilities, developer)

    def plan(self):
        plan = self.preview_generator.plan(self.spec())
        if plan != self.review_plan:
            self.validation = None
        self.review_plan = plan
        return self.review_plan

    def validate(self):
        plan = self.plan()
        generator = self.generator_factory()
        validation = generator.validate(plan)
        self.validation = validation
        return validation

    @property
    def validated(self):
        return bool(self.validation and self.validation.ok and self.review_plan)

    def create_folder(self, parent, *, overwrite=False):
        if not self.validated:
            return WorkbenchWriteResult(False, error="Validate Project first.")
        generator = self.generator_factory()
        destination = Path(parent).expanduser().resolve() / (
            self.review_plan.spec.identity.folder_name
        )
        result = generator.write(self.review_plan, destination, overwrite=overwrite)
        if result.ok:
            self.generated_folder = result.path
            return WorkbenchWriteResult(True, result.path, result.digest)
        return WorkbenchWriteResult(False, error=result.error)

    def build_zip(self, destination, *, overwrite=False):
        if not self.validated:
            return WorkbenchWriteResult(False, error="Validate Project first.")
        with tempfile.TemporaryDirectory(prefix="susadb-plugin-project-zip-") as value:
            parent = Path(value)
            generator = self.generator_factory()
            folder = parent / self.review_plan.spec.identity.folder_name
            written = generator.write(self.review_plan, folder)
            if not written.ok:
                return WorkbenchWriteResult(False, error=written.error)
            source = PluginWorkbenchSource.selected(folder)
            snapshot = PluginWorkbenchAnalyzer(
                official_identities=generator.official_identities
            ).analyze(source)
            result = PluginWorkbenchPackageBuilder().build(
                source, snapshot, destination, overwrite=overwrite
            )
            if not result.ok:
                return result
            # The canonical package builder validates the completed archive
            # before its atomic replacement. A failed validation therefore
            # preserves any existing destination.
            self.generated_zip = result.path
            return result

    def export_brief(self, destination, *, overwrite=False):
        if not self.validated:
            return WorkbenchWriteResult(False, error="Validate Project first.")
        plan = self.review_plan
        result = atomic_write_report(
            destination,
            plan.file("DEVELOPER_BRIEF.md").text,
            overwrite=overwrite,
        )
        return result
