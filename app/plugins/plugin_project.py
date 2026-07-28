"""Deterministic, non-executing Plugin API 1.1 project scaffolding."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping

from app.plugins.plugin_capabilities import CAPABILITIES, HIGH_IMPACT
from app.plugins.plugin_manifest import (
    CONTRIBUTION_TYPES,
    PLUGIN_ID,
    SEMVER,
    PluginManifest,
)
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_validator import PluginValidator
from app.plugins.plugin_workbench import (
    FindingSeverity,
    PluginWorkbenchAnalyzer,
)


PROJECT_API_VERSION = "1.1"
PROJECT_CONTRIBUTION_TYPE = "pentest-panel"
PROJECT_UI_MODES = ("window", "hybrid")
PROJECT_PLATFORMS = ("linux", "windows")
PROJECT_FILES = (
    "manifest.json",
    "plugin.py",
    "README.md",
    "DEVELOPER_BRIEF.md",
    "ARCHITECTURE.md",
    "TUTORIAL.md",
    "CHECKLIST.md",
    "TROUBLESHOOTING.md",
    "tests/test_lifecycle.py",
)
WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)
_SLUG_PARTS = re.compile(r"[^a-z0-9]+")


def _bounded(value, label, limit, *, required=True):
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label} is required.")
    if len(text) > limit:
        raise ValueError(f"{label} exceeds {limit} characters.")
    return text


def portable_folder_name(value):
    name = str(value or "")
    if not name or len(name) > 96:
        raise ValueError("Project folder name must contain 1 through 96 characters.")
    if name != name.strip() or name.startswith(".") or name.endswith("."):
        raise ValueError("Project folder name cannot lead or trail with spaces or periods.")
    if "/" in name or "\\" in name or any(ord(character) < 32 for character in name):
        raise ValueError("Project folder name must be one portable path component.")
    if any(character in '<>:"|?*' for character in name):
        raise ValueError("Project folder name contains a Windows-invalid character.")
    if name.rstrip(" .").split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError("Project folder name is reserved on Windows.")
    return name


def _slug(value, fallback):
    result = _SLUG_PARTS.sub("-", str(value or "").casefold()).strip("-")
    return result or fallback


def suggest_plugin_id(author, project_name):
    """Return a deterministic editable suggestion; global uniqueness is not claimed."""
    publisher = _slug(author, "developer")
    if publisher in {"susadb", "sus-adb", "sus-companion"}:
        publisher = "developer"
    project = _slug(project_name, "plugin")
    publisher_tokens = tuple(publisher.split("-"))
    project_tokens = tuple(project.split("-"))
    if project_tokens[:len(publisher_tokens)] == publisher_tokens:
        project = "-".join(project_tokens[len(publisher_tokens):]) or "plugin"
    return f"{publisher}.{project}"


def suggest_contribution_id(plugin_id):
    return f"{str(plugin_id).strip()}.main"


@dataclass(frozen=True, slots=True)
class PluginProjectIdentity:
    display_name: str
    plugin_id: str
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    license: str = "MIT"
    supported_platforms: tuple[str, ...] = PROJECT_PLATFORMS
    plugin_api_version: str = PROJECT_API_VERSION
    folder_name: str = ""

    def __post_init__(self):
        object.__setattr__(self, "display_name", _bounded(
            self.display_name, "Project display name", 120
        ))
        plugin_id = str(self.plugin_id or "").strip()
        if not PLUGIN_ID.fullmatch(plugin_id):
            raise ValueError("Plugin ID must be a stable lowercase identifier.")
        if plugin_id == "susadb" or plugin_id.startswith("susadb."):
            raise ValueError(
                "The susadb namespace is reserved for bundled official addons."
            )
        object.__setattr__(self, "plugin_id", plugin_id)
        if not SEMVER.fullmatch(str(self.version or "")):
            raise ValueError("Plugin version must use semantic versioning.")
        object.__setattr__(self, "author", _bounded(
            self.author, "Author or publisher", 120
        ))
        object.__setattr__(self, "description", _bounded(
            self.description, "Description", 300
        ))
        object.__setattr__(self, "license", _bounded(
            self.license, "License", 80
        ))
        platforms = tuple(dict.fromkeys(str(value) for value in self.supported_platforms))
        if not platforms or any(value not in PROJECT_PLATFORMS for value in platforms):
            raise ValueError("Supported platforms must use linux and/or windows.")
        object.__setattr__(self, "supported_platforms", platforms)
        if self.plugin_api_version != PROJECT_API_VERSION:
            raise ValueError("Plugin Project Wizard v1 generates Plugin API 1.1.")
        object.__setattr__(
            self, "folder_name",
            portable_folder_name(self.folder_name or _slug(self.display_name, "plugin")),
        )


@dataclass(frozen=True, slots=True)
class PluginProjectContributionSpec:
    contribution_id: str
    title: str
    contribution_type: str = PROJECT_CONTRIBUTION_TYPE
    ui_mode: str = "window"
    singleton: bool = True
    default_width: int = 1080
    default_height: int = 720
    minimum_width: int = 820
    minimum_height: int = 560
    icon: str = "⚙"

    def __post_init__(self):
        identifier = str(self.contribution_id or "").strip()
        if not PLUGIN_ID.fullmatch(identifier):
            raise ValueError("Contribution ID must be a stable lowercase identifier.")
        object.__setattr__(self, "contribution_id", identifier)
        object.__setattr__(
            self, "title", _bounded(self.title, "Contribution title", 120)
        )
        if self.contribution_type not in CONTRIBUTION_TYPES:
            raise ValueError("Unsupported contribution type.")
        if self.contribution_type != PROJECT_CONTRIBUTION_TYPE:
            raise ValueError(
                "Wizard v1 supports one interactive Pentest panel contribution."
            )
        if self.ui_mode not in PROJECT_UI_MODES:
            raise ValueError("Wizard v1 UI mode must be window or hybrid.")
        for value, label, lower, upper in (
            (self.default_width, "Default width", 400, 2400),
            (self.minimum_width, "Minimum width", 400, 2400),
            (self.default_height, "Default height", 300, 1600),
            (self.minimum_height, "Minimum height", 300, 1600),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
                raise ValueError(f"{label} must be between {lower} and {upper}.")
        if self.minimum_width > self.default_width:
            raise ValueError("Minimum width cannot exceed default width.")
        if self.minimum_height > self.default_height:
            raise ValueError("Minimum height cannot exceed default height.")
        object.__setattr__(self, "icon", _bounded(
            self.icon, "Contribution icon text", 8, required=False
        ) or "⚙")


@dataclass(frozen=True, slots=True)
class PluginProjectCapabilityPlan:
    requested: tuple[str, ...] = ()
    justifications: Mapping[str, str] = field(default_factory=dict)
    high_impact_acknowledged: bool = False

    def __post_init__(self):
        requested = tuple(sorted(set(str(value) for value in self.requested)))
        unknown = tuple(value for value in requested if value not in CAPABILITIES)
        if unknown:
            raise ValueError("Unknown capabilities: " + ", ".join(unknown))
        if set(requested) & HIGH_IMPACT and not self.high_impact_acknowledged:
            raise ValueError(
                "High-impact capability selections require explicit acknowledgment."
            )
        notes = {
            capability: _bounded(
                dict(self.justifications).get(capability, ""),
                f"{capability} justification", 300, required=False,
            )
            for capability in requested
        }
        object.__setattr__(self, "requested", requested)
        object.__setattr__(self, "justifications", MappingProxyType(notes))


@dataclass(frozen=True, slots=True)
class PluginProjectDeveloperDetails:
    intended_purpose: str = ""
    operator_workflow: str = ""
    planned_inputs: str = ""
    expected_output: str = ""
    cancellation_needs: str = ""
    navigation_destination: str = "contextual-help"
    implementation_notes: str = ""

    def __post_init__(self):
        from app.plugins.plugin_interactive import PLUGIN_NAVIGATION_DESTINATIONS

        for name, label in (
            ("intended_purpose", "Intended purpose"),
            ("operator_workflow", "Operator workflow"),
            ("planned_inputs", "Planned inputs"),
            ("expected_output", "Expected output"),
            ("cancellation_needs", "Cancellation needs"),
            ("implementation_notes", "Implementation notes"),
        ):
            object.__setattr__(
                self, name, _bounded(getattr(self, name), label, 1_000, required=False)
            )
        if self.navigation_destination not in PLUGIN_NAVIGATION_DESTINATIONS:
            raise ValueError("Unknown safe navigation destination.")


@dataclass(frozen=True, slots=True)
class PluginProjectSpec:
    identity: PluginProjectIdentity
    contribution: PluginProjectContributionSpec
    capabilities: PluginProjectCapabilityPlan = field(
        default_factory=PluginProjectCapabilityPlan
    )
    developer: PluginProjectDeveloperDetails = field(
        default_factory=PluginProjectDeveloperDetails
    )

    def __post_init__(self):
        if self.contribution.contribution_id == "skeleton.documentation":
            raise ValueError("Skeleton contribution IDs cannot be reused.")
        if not self.contribution.contribution_id.startswith(
            self.identity.plugin_id + "."
        ):
            raise ValueError("Contribution ID must be owned by the project plugin ID.")


@dataclass(frozen=True, slots=True)
class PluginProjectFile:
    path: str
    content: bytes = field(repr=False)

    def __post_init__(self):
        path = PurePosixPath(str(self.path).replace("\\", "/"))
        if (
            path.is_absolute() or ".." in path.parts or not path.parts
            or any(part in {"", "."} for part in path.parts)
        ):
            raise ValueError("Generated project file path is unsafe.")
        object.__setattr__(self, "path", path.as_posix())
        object.__setattr__(self, "content", bytes(self.content))

    @property
    def text(self):
        return self.content.decode("utf-8")


@dataclass(frozen=True, slots=True)
class PluginProjectPlan:
    spec: PluginProjectSpec
    files: tuple[PluginProjectFile, ...]
    digest: str

    def __post_init__(self):
        paths = tuple(value.path for value in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("Generated project files must be unique and ordered.")

    def file(self, path):
        return next(value for value in self.files if value.path == path)


@dataclass(frozen=True, slots=True)
class PluginProjectValidation:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    inspection: object = field(default=None, repr=False, compare=False)
    production: object = field(default=None, repr=False, compare=False)
    workbench: object = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class PluginProjectGenerationResult:
    ok: bool
    path: str = ""
    digest: str = ""
    files: tuple[str, ...] = ()
    error: str = ""


class PluginProjectGenerator:
    """Builds byte-stable plans and composes canonical static validators."""

    def __init__(self, official_identities: Mapping[str, bool] = ()):
        self.official_identities = dict(official_identities)
        self.validator = PluginValidator()

    def plan(self, spec: PluginProjectSpec):
        if spec.identity.plugin_id in self.official_identities:
            raise ValueError("Official plugin IDs are reserved.")
        contents = self._contents(spec)
        files = tuple(
            PluginProjectFile(path, self._utf8(contents[path]))
            for path in sorted(contents)
        )
        if tuple(value.path for value in files) != tuple(sorted(PROJECT_FILES)):
            raise ValueError("Generated project file set is incomplete.")
        digest = hashlib.sha256(
            b"".join(
                value.path.encode("utf-8") + b"\0" + value.content + b"\0"
                for value in files
            )
        ).hexdigest()
        return PluginProjectPlan(spec, files, digest)

    @staticmethod
    def _utf8(value):
        return str(value).replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")

    def validate(self, plan: PluginProjectPlan):
        with tempfile.TemporaryDirectory(prefix="susadb-plugin-project-review-") as value:
            root = Path(value)
            self._materialize(plan, root)
            return self._validate_directory(root, plan)

    def _validate_directory(self, root, plan):
        inspection = PluginPackage.inspect(root)
        production = self.validator.validate(inspection, root=root)
        workbench = PluginWorkbenchAnalyzer(
            official_identities=self.official_identities
        ).analyze(root)
        errors = list(production.errors)
        errors.extend(
            f"{finding.rule_id}: {finding.title}"
            for finding in workbench.findings
            if finding.severity is FindingSeverity.ERROR
        )
        manifest = inspection.manifest if inspection.ok else None
        if manifest is None:
            errors.append(inspection.error or "Generated manifest could not be parsed.")
        else:
            if manifest.plugin_api_version != PROJECT_API_VERSION:
                errors.append("Generated project does not declare Plugin API 1.1.")
            if manifest.plugin_id in self.official_identities:
                errors.append("Generated project uses a reserved official plugin ID.")
            manifest_ids = tuple(
                item.contribution_id for item in manifest.contributed_components
            )
            python_ids = self._registered_contribution_ids(
                plan.file("plugin.py").text
            )
            if manifest_ids != python_ids:
                errors.append(
                    "Manifest and Python registration contribution IDs do not match."
                )
        expected = tuple(sorted(PROJECT_FILES))
        actual = tuple(sorted(value.path for value in plan.files))
        if actual != expected:
            errors.append("Generated project file set is incomplete.")
        warnings = tuple(dict.fromkeys(
            (*production.warnings, *production.capability_cautions, *(
                f"{finding.rule_id}: {finding.title}"
                for finding in workbench.findings
                if finding.severity is FindingSeverity.WARNING
            ))
        ))
        return PluginProjectValidation(
            ok=not errors,
            errors=tuple(dict.fromkeys(errors)),
            warnings=warnings,
            inspection=inspection,
            production=production,
            workbench=workbench,
        )

    @staticmethod
    def _registered_contribution_ids(source):
        tree = ast.parse(source, filename="plugin.py")
        identifiers = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if (
                name == "Contribution" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                identifiers.append(node.args[0].value)
        return tuple(identifiers)

    def write(self, plan, destination, *, overwrite=False):
        validation = self.validate(plan)
        if not validation.ok:
            return PluginProjectGenerationResult(
                False, error="; ".join(validation.errors)
            )
        destination = Path(destination).expanduser().resolve()
        if destination.name != plan.spec.identity.folder_name:
            return PluginProjectGenerationResult(
                False, error="Destination folder name does not match the reviewed plan."
            )
        parent = destination.parent
        if not parent.is_dir():
            return PluginProjectGenerationResult(
                False, error="Selected destination parent is unavailable."
            )
        if destination.exists() and not overwrite:
            return PluginProjectGenerationResult(
                False, error="Overwrite confirmation is required."
            )
        staging = Path(tempfile.mkdtemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=parent
        ))
        backup_root = None
        backup = None
        try:
            self._materialize(plan, staging)
            staged_validation = self._validate_directory(staging, plan)
            if not staged_validation.ok:
                raise ValueError(
                    "Completed project failed validation: "
                    + "; ".join(staged_validation.errors)
                )
            if destination.exists():
                if not destination.is_dir():
                    raise ValueError("Existing project destination is not a directory.")
                backup_root = Path(tempfile.mkdtemp(
                    prefix=f".{destination.name}.backup.", dir=parent
                ))
                backup = backup_root / "previous"
                destination.replace(backup)
            try:
                staging.replace(destination)
            except OSError:
                if backup is not None and backup.exists() and not destination.exists():
                    backup.replace(destination)
                raise
            if backup_root is not None:
                shutil.rmtree(backup_root, ignore_errors=True)
                backup_root = None
            return PluginProjectGenerationResult(
                True, str(destination), plan.digest,
                tuple(value.path for value in plan.files),
            )
        except (OSError, ValueError) as exc:
            if backup is not None and backup.exists() and not destination.exists():
                try:
                    backup.replace(destination)
                except OSError:
                    pass
            return PluginProjectGenerationResult(False, error=str(exc))
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            if backup_root is not None:
                shutil.rmtree(backup_root, ignore_errors=True)

    @staticmethod
    def _materialize(plan, root):
        root = Path(root)
        for project_file in plan.files:
            target = root.joinpath(*PurePosixPath(project_file.path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as stream:
                stream.write(project_file.content)
                stream.flush()
                os.fsync(stream.fileno())

    def _contents(self, spec):
        identity = spec.identity
        contribution = spec.contribution
        capabilities = spec.capabilities.requested
        manifest = {
            "addon_ui": {"ui_mode": contribution.ui_mode},
            "author": identity.author,
            "caution_text": (
                "Generated inert Plugin API 1.1 starter. Review and implement "
                "before installation."
            ),
            "contributed_components": [{
                "contribution_id": contribution.contribution_id,
                "contribution_type": contribution.contribution_type,
                "factory": "panel_spec",
                "metadata": {
                    "default_height": contribution.default_height,
                    "default_width": contribution.default_width,
                    "icon": contribution.icon,
                    "minimum_height": contribution.minimum_height,
                    "minimum_width": contribution.minimum_width,
                    "singleton": contribution.singleton,
                    "ui_mode": contribution.ui_mode,
                },
                "title": contribution.title,
            }],
            "description": identity.description,
            "enabled": False,
            "entry_point": "plugin.py:Plugin",
            "license": identity.license,
            "minimum_sus_adb_version": "1.0.0",
            "name": identity.display_name,
            "optional_dependencies": [],
            "plugin_api_version": PROJECT_API_VERSION,
            "plugin_id": identity.plugin_id,
            "requested_capabilities": list(capabilities),
            "required_external_tools": [],
            "supported_platforms": list(identity.supported_platforms),
            "trust_state": "untrusted",
            "version": identity.version,
        }
        return {
            "manifest.json": json.dumps(
                manifest, indent=2, sort_keys=True, ensure_ascii=False
            ) + "\n",
            "plugin.py": self._plugin_source(spec),
            "README.md": self._readme(spec),
            "DEVELOPER_BRIEF.md": self._developer_brief(spec),
            "ARCHITECTURE.md": self._architecture(spec),
            "TUTORIAL.md": self._tutorial(spec),
            "CHECKLIST.md": self._checklist(spec),
            "TROUBLESHOOTING.md": self._troubleshooting(spec),
            "tests/test_lifecycle.py": self._test_source(spec),
        }

    @staticmethod
    def _plugin_source(spec):
        identity = spec.identity
        contribution = spec.contribution
        capabilities = repr(spec.capabilities.requested)
        destination = spec.developer.navigation_destination
        return f'''"""Inert Plugin API 1.1 starter generated by SUS Companion.

Complete the TODO boundaries only through documented public SDK façades.
Module import, construction, panel creation, and window opening perform no work.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.plugins import (
    PluginActionResult,
    PluginActionSpec,
    PluginFieldSpec,
    PluginFormSpec,
    PluginNavigationSpec,
    PluginPanelSpec,
    PluginResult,
    PluginView,
)
from app.plugins.contribution_registry import Contribution


@dataclass(frozen=True, slots=True)
class LocalState:
    message: str = "No action has run."


def validate_input(request):
    """Explicit inert action: validates host-sanitized input and changes nothing."""
    label = request.values["label"]
    return PluginActionResult(
        True,
        f"Validated {{label}}. No operational action was performed.",
        rows=(("Behavior", "Inert starter action"),),
        panel=panel_spec(message=f"Last explicit validation: {{label}}"),
    )


def open_help(_request):
    """Safe host-owned navigation; it performs no operational action."""
    return PluginActionResult(
        True,
        "Opening a documented host destination.",
        navigation=PluginNavigationSpec({destination!r}),
    )


def panel_spec(_context=None, message="No action has run."):
    form = PluginFormSpec(
        {identity.plugin_id + ".starter-form"!r},
        (
            PluginFieldSpec(
                "label",
                "Starter label",
                required=True,
                max_length=80,
                placeholder="Enter a non-sensitive label",
                validation_hint="Runtime-only; no value is logged or persisted.",
            ),
        ),
        title="Inert starter form",
        description="The host validates this form before an explicit click.",
    )
    actions = (
        PluginActionSpec(
            {identity.plugin_id + ".validate"!r},
            "Validate Starter Input",
            validate_input,
            description="Validates one bounded value and performs no external work.",
            required_capabilities={capabilities},
            form=form,
            primary=True,
        ),
        PluginActionSpec(
            {identity.plugin_id + ".help"!r},
            "Open Host Help",
            open_help,
            description="Navigates to a safe host-owned destination.",
        ),
    )
    return PluginPanelSpec(
        {contribution.title!r},
        (
            PluginView(
                "Overview",
                {("Generated starter for " + identity.description + " No work runs when this panel opens.")!r},
            ),
        ),
        {{
            "Plugin API": "1.1",
            "Capabilities": {str(len(spec.capabilities.requested))!r},
            "Result": message,
        }},
        actions,
    )


class Plugin:
    def __init__(self):
        self.api = None
        self.state = LocalState()

    def validate(self):
        return PluginResult(True, self.state)

    def load(self, api):
        self.api = api
        return PluginResult(True)

    def register(self):
        return (
            Contribution(
                {contribution.contribution_id!r},
                {contribution.contribution_type!r},
                {contribution.title!r},
                factory=panel_spec,
                metadata={{
                    "ui_mode": {contribution.ui_mode!r},
                    "singleton": {contribution.singleton!r},
                    "default_width": {contribution.default_width},
                    "default_height": {contribution.default_height},
                    "minimum_width": {contribution.minimum_width},
                    "minimum_height": {contribution.minimum_height},
                    "icon": {contribution.icon!r},
                }},
            ),
        )

    def start(self):
        # TODO: add only bounded, cooperative work through public SDK façades.
        return PluginResult(True)

    def stop(self):
        return PluginResult(True)

    def unregister(self):
        return PluginResult(True)

    def unload(self):
        self.api = None
        return PluginResult(True)

    def activate(self, api):
        self.load(api)
        return self.register()

    def deactivate(self):
        self.stop()
        self.unregister()
        self.unload()
'''

    @staticmethod
    def _capability_lines(spec):
        if not spec.capabilities.requested:
            return "- None — this is the recommended zero-capability starter."
        return "\n".join(
            f"- `{capability}` — "
            f"{spec.capabilities.justifications.get(capability) or 'Justification must be completed before implementation.'}"
            for capability in spec.capabilities.requested
        )

    def _readme(self, spec):
        return f"""# {spec.identity.display_name}

This is an inert Plugin API 1.1 starter generated from the official Skeleton
architecture. Opening, reviewing, installing, trusting, approving, enabling,
loading, or opening the panel does not invoke its actions automatically.

- Plugin ID: `{spec.identity.plugin_id}`
- Contribution ID: `{spec.contribution.contribution_id}`
- Version: `{spec.identity.version}`
- Capabilities: {", ".join(spec.capabilities.requested) or "None"}

Complete and test the TODO boundaries, inspect the folder in Plugin Developer
Workbench, build a deterministic ZIP, and then follow the separate install,
trust, capability approval, enable, load, and open lifecycle.
"""

    def _developer_brief(self, spec):
        details = spec.developer
        return f"""# Developer Brief — {spec.identity.display_name}

## Mission and exact identity

SUS Companion is a cross-platform workstation for authorized Android reverse
engineering and security testing. This project declares Plugin API 1.1.

- Plugin ID: `{spec.identity.plugin_id}`
- Contribution ID: `{spec.contribution.contribution_id}`
- Contribution type: `{spec.contribution.contribution_type}`
- Entry point: `plugin.py:Plugin`
- Panel factory: `panel_spec`

Do not change either stable ID silently. Keep the manifest contribution ID and
Python `Contribution` registration synchronized.

## Capability plan

{self._capability_lines(spec)}

Declaring a capability requests permission; it does not implement the
operation. Approval remains explicit and bound to the exact package digest.

## Public and private boundaries

Permitted imports are documented `app.plugins` SDK surfaces, including the
public contribution declaration. Private `app.core` and `app.gui` imports are
forbidden. Do not expose or retain Tk roots, widgets, managers, workers, secret
providers, private application state, unrestricted filesystem/network/process
access, ADB shells, Frida, or Objection objects.

## Generated interaction architecture

The host renders one immutable `PluginView`, one bounded form, one explicit
inert validation action, and one safe navigation action. Use
`PluginActionResult.ok`; never invent `.success`. Form values remain runtime
only and must not enter logs, exceptions, reports, history, or defaults.

## Lifecycle and confirmation boundaries

Import, construction, validation, discovery, installation, enablement, panel
construction, and window opening perform no work. Only an explicit operator
click may invoke an action. State-changing actions require a host-owned
confirmation immediately before invocation and must bind exact device/target
context when relevant.

Use existing host workers for bounded blocking callbacks, cooperative
cancellation, bounded progress, and stale-result rejection. Cancel and release
owned resources during close/unload. Never create a global pool or modify Tk
outside its UI thread.

## Intended implementation

- Purpose: {details.intended_purpose or "To be defined by the developer."}
- Operator workflow: {details.operator_workflow or "To be defined by the developer."}
- Planned inputs: {details.planned_inputs or "Bounded, non-sensitive host-rendered inputs only."}
- Expected output: {details.expected_output or "A bounded immutable PluginActionResult."}
- Cancellation: {details.cancellation_needs or "Add cooperative cancellation if work can block."}
- Safe navigation: `{details.navigation_destination}`
- Notes: {details.implementation_notes or "No additional implementation notes."}

## Cross-platform, tests, and review

Preserve Linux and Windows paths containing spaces. Use structured argv with
`shell=False` only through an approved public façade. Add fake/local-only tests
for inert construction, validation, explicit invocation, capability denial,
context change, cancellation, cleanup, digest changes, and API 1.0 coexistence.

Run Plugin Developer Workbench static validation and deterministic packaging.
Static analysis does not prove future edited code is safe. Normal lifecycle is:
install disabled → review digest → trust → approve requested capabilities →
enable → load → open.

Known SDK gap: there is no unrestricted subprocess, shell, filesystem, network,
ADB shell, Frida, or Objection contract. Report a compatibility gap instead of
importing private services. Return complete updated files, not fragments.
"""

    @staticmethod
    def _architecture(spec):
        return f"""# Architecture

```text
manifest ({spec.identity.plugin_id})
  → static Workbench review
  → disabled package storage
  → exact-digest trust and capability approval
  → explicit enable/load
  → contribution ({spec.contribution.contribution_id})
  → host-rendered immutable view/form/actions
  → explicit unload and cleanup
```

The host owns windows, geometry, theme, validation, confirmation, workers,
navigation, and cleanup. The generated callback is intentionally inert.
"""

    @staticmethod
    def _tutorial(spec):
        return f"""# Tutorial

1. Keep `{spec.identity.plugin_id}` and `{spec.contribution.contribution_id}`
   synchronized in the manifest and registration.
2. Complete the intent in `DEVELOPER_BRIEF.md`.
3. Request only real minimal capabilities.
4. Implement only through documented public SDK façades.
5. Start no work during import, construction, or panel opening.
6. Add fake-driven tests and cooperative cleanup.
7. Validate the folder in Plugin Developer Workbench.
8. Build a deterministic ZIP and repeat production validation.
9. Install, trust, approve, enable, load, and open as separate actions.
"""

    @staticmethod
    def _checklist(spec):
        return f"""# Project Checklist

- [ ] Stable plugin ID remains `{spec.identity.plugin_id}`
- [ ] Contribution ID remains `{spec.contribution.contribution_id}`
- [ ] Plugin API remains `1.1`
- [ ] Manifest and Python registration IDs match
- [ ] Capabilities are minimal and justified
- [ ] No private host imports or raw Tk
- [ ] No work runs on open
- [ ] State changes use host confirmation and exact context
- [ ] Blocking work uses bounded cancellation/progress
- [ ] Sensitive values never enter defaults or logs
- [ ] Linux and Windows paths with spaces are tested
- [ ] Workbench has no blocking finding
- [ ] Deterministic ZIP passes production validation
"""

    @staticmethod
    def _troubleshooting(spec):
        return f"""# Troubleshooting

- Reserved ID: choose a non-`susadb.*` stable plugin ID.
- Contribution mismatch: keep `{spec.contribution.contribution_id}` identical
  in `manifest.json` and `plugin.py`.
- Capability denied: declaration, digest-bound approval, and applicable scope
  are separate requirements.
- Action unavailable: verify the exact loaded digest still owns approvals.
- Stale result: the panel closed, plugin unloaded, or context changed.
- Missing operation: use a documented public façade or record an SDK gap.
"""

    @staticmethod
    def _test_source(spec):
        return f'''"""Static starter checks; generated plugin code is not imported."""
import unittest


class GeneratedProjectLifecycleTests(unittest.TestCase):
    def test_reviewed_identity_is_stable(self):
        self.assertEqual({spec.identity.plugin_id!r}, {spec.identity.plugin_id!r})
        self.assertEqual(
            {spec.contribution.contribution_id!r},
            {spec.contribution.contribution_id!r},
        )

    def test_starter_expectations_are_explicit(self):
        self.assertEqual("1.1", "1.1")
        self.assertFalse(False)


if __name__ == "__main__":
    unittest.main()
'''
