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

EXPECTED_TEST_FILE = "tests/test_lifecycle.py"
UNDECLARED_EXECUTABLE_PREFIX = "Undeclared executable/native files: "


@dataclass(frozen=True, slots=True)
class PluginProjectSuggestion:
    current: str
    suggested: str
    requires_confirmation: bool


@dataclass(frozen=True, slots=True)
class PluginProjectValidationAdvisory:
    title: str
    detail: str
    rule_ids: tuple[str, ...] = ()


def validation_advisories(validation):
    """Deduplicate raw validator/Workbench warnings for Wizard presentation."""
    advisories = {}
    warning_keys = {}

    def add(key, title, detail, *rule_ids):
        previous = advisories.get(key)
        origins = tuple(dict.fromkeys(
            (*(previous.rule_ids if previous else ()), *filter(None, rule_ids))
        ))
        advisories[key] = PluginProjectValidationAdvisory(
            title, detail, origins
        )

    def project_warning(warning, rule_id=""):
        keys = []
        if warning.startswith(UNDECLARED_EXECUTABLE_PREFIX):
            paths = tuple(
                value.strip()
                for value in warning.removeprefix(
                    UNDECLARED_EXECUTABLE_PREFIX
                ).split(",")
                if value.strip()
            )
            for path in paths:
                if path == EXPECTED_TEST_FILE:
                    key = ("expected-test", path)
                    add(
                        key,
                        "Expected generated test file",
                        f"{path} is included for developer lifecycle testing. "
                        "It does not block project generation and is not "
                        "executed by the Wizard.",
                        rule_id,
                    )
                else:
                    key = ("undeclared-executable", path)
                    add(
                        key,
                        "Undeclared executable or native file",
                        f"{path} is not declared by the plugin manifest. "
                        "Review it before packaging.",
                        rule_id,
                    )
                keys.append(key)
        else:
            key = ("warning", warning)
            add(
                key, "Production validation advisory", warning, rule_id
            )
            keys.append(key)
        return tuple(keys)

    production = getattr(validation, "production", None)
    production_warnings = tuple(getattr(production, "warnings", ()))
    if production is not None:
        for warning in production_warnings:
            warning_keys[warning] = project_warning(
                warning, "PluginValidator"
            )
        for caution in getattr(production, "capability_cautions", ()):
            capability = caution.split(" ", 1)[0]
            add(
                ("capability", capability),
                f"Capability caution · {capability}",
                caution + " Declaring it does not implement the operation.",
                "PluginValidator",
            )
    else:
        for warning in getattr(validation, "warnings", ()):
            if not warning.startswith("VAL002:"):
                warning_keys[warning] = project_warning(warning)

    workbench = getattr(validation, "workbench", None)
    for finding in getattr(workbench, "findings", ()):
        if getattr(getattr(finding, "severity", None), "value", "") != "warning":
            continue
        if finding.rule_id == "VAL002":
            keys = warning_keys.get(finding.explanation)
            if keys is None:
                keys = project_warning(finding.explanation, finding.rule_id)
            else:
                for key in keys:
                    previous = advisories[key]
                    add(
                        key, previous.title, previous.detail, finding.rule_id
                    )
            continue
        add(
            ("workbench", finding.rule_id, finding.path, finding.line),
            finding.title,
            finding.explanation,
            finding.rule_id,
        )
    return tuple(advisories.values())


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
    plugin_id_locked: bool = False
    last_suggested_plugin_id: str = ""
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    license: str = "MIT"
    platforms: tuple[str, ...] = ("linux", "windows")
    folder_name: str = ""
    folder_name_locked: bool = False
    last_suggested_folder_name: str = ""
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

    def preview_plugin_id_suggestion(self):
        value = suggest_plugin_id(self.draft.author, self.draft.project_name)
        current = self.draft.plugin_id
        requires = bool(
            current
            and (
                self.draft.plugin_id_locked
                or current != self.draft.last_suggested_plugin_id
            )
            and current != value
        )
        return PluginProjectSuggestion(current, value, requires)

    def apply_plugin_id_suggestion(self, *, confirmed=False):
        preview = self.preview_plugin_id_suggestion()
        if preview.requires_confirmation and not confirmed:
            return None
        self.set_plugin_id(preview.suggested, manual=False)
        return preview.suggested

    @staticmethod
    def folder_suggestion(plugin_id):
        return str(plugin_id or "").replace(".", "-") or "plugin-project"

    def preview_folder_suggestion(self):
        value = self.folder_suggestion(self.draft.plugin_id)
        current = self.draft.folder_name
        requires = bool(
            current
            and (
                self.draft.folder_name_locked
                or current != self.draft.last_suggested_folder_name
            )
            and current != value
        )
        return PluginProjectSuggestion(current, value, requires)

    def apply_folder_suggestion(self, *, confirmed=False):
        preview = self.preview_folder_suggestion()
        if preview.requires_confirmation and not confirmed:
            return None
        self.set_folder_name(preview.suggested, manual=False)
        return preview.suggested

    def set_plugin_id(self, value, *, manual=True):
        old = self.draft.plugin_id
        previous_suggestion = suggest_contribution_id(old) if old else ""
        value = str(value)
        self.draft.plugin_id = value
        if manual:
            self.draft.plugin_id_locked = bool(value.strip())
        else:
            self.draft.plugin_id_locked = False
            self.draft.last_suggested_plugin_id = value
        if (
            not self.draft.contribution_locked
            and (
                not self.draft.contribution_id
                or self.draft.contribution_id == previous_suggestion
            )
        ):
            self.draft.contribution_id = suggest_contribution_id(value) if value else ""
        if (
            not self.draft.folder_name_locked
            and self.draft.last_suggested_folder_name
            and self.draft.folder_name
            == self.draft.last_suggested_folder_name
        ):
            folder = self.folder_suggestion(value)
            self.draft.folder_name = folder
            self.draft.last_suggested_folder_name = folder
        self._invalidate()

    def set_folder_name(self, value, *, manual=True):
        value = str(value)
        self.draft.folder_name = value
        if manual:
            self.draft.folder_name_locked = bool(value.strip())
        else:
            self.draft.folder_name_locked = False
            self.draft.last_suggested_folder_name = value
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
        self.generated_folder = ""
        self.generated_zip = ""

    @property
    def custom_folder_retained(self):
        return bool(
            self.draft.folder_name_locked
            and self.draft.folder_name
            != self.folder_suggestion(self.draft.plugin_id)
        )

    def advisories(self):
        if self.validation is None:
            return ()
        return validation_advisories(self.validation)

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
